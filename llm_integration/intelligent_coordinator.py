# enhanced_command_processor.py - LLM-powered MCP tool integration

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import os
import re
from sqlalchemy.orm import Session

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)

from llm_integration.mixins.parsing_mixin import ParsingMixin
from llm_integration.mixins.tools_mixin import ToolsMixin
from llm_integration.mixins.workout_mixin import WorkoutMixin
from llm_integration.mixins.fallback_mixin import FallbackMixin


class IntelligentCoordinator(ParsingMixin, ToolsMixin, WorkoutMixin, FallbackMixin):
    def __init__(self, calendar_client, meet_client, sms_client):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        # Lazy-initialized external integrations
        self.strava_client = None

        # Initialize Claude client
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self._llm_enabled = True
            logger.info("✅ LLM integration enabled with Claude API")
        else:
            self.claude_client = None
            self._llm_enabled = False
            logger.info("📝 LLM integration disabled - using basic processing")

        # Define available MCP tools (dynamic from registry if present)
        self.available_tools = self._define_mcp_tools()
        # Provide explicit refresh helper for test environment changes
        self.refresh_llm_status()

    def refresh_llm_status(self):  # pragma: no cover simple setter
        if os.getenv("ANTHROPIC_API_KEY") and self.claude_client is None and ANTHROPIC_AVAILABLE:
            try:
                import anthropic
                self.claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                self._llm_enabled = True
            except Exception:
                self._llm_enabled = False
        else:
            self._llm_enabled = bool(os.getenv("ANTHROPIC_API_KEY") and self.claude_client)

    @property
    def llm_enabled(self) -> bool:  # dynamic view so late env var injection is reflected
        if os.getenv("ANTHROPIC_API_KEY"):
            return True
        return getattr(self, "_llm_enabled", False)

    @llm_enabled.setter
    def llm_enabled(self, value: bool):  # allow explicit overrides in services/tests
        self._llm_enabled = value

    # Backward compatibility for tests expecting process_command_with_llm
    async def process_command_with_llm(self, *args, **kwargs):  # pragma: no cover - compatibility shim
        message = kwargs.get("message") or (args[0] if args else "")
        user = kwargs.get("user") or kwargs.get("team_member") or (args[1] if len(args) > 1 else None)
        conversation = kwargs.get("conversation") or kwargs.get("conv") or (args[2] if len(args) > 2 else None)
        db = kwargs.get("db") or (args[3] if len(args) > 3 else None)
        return await self.process_message(message, user, conversation, db)
        
    def _define_mcp_tools(self) -> List[Dict]:
        """Obtain MCP tool definitions dynamically from registry, with fallback."""
        try:
            from mcp_integration.base import tool_registry  # local import to avoid cycles
            listed = tool_registry.list()
            if listed:
                return listed
        except Exception:
            pass
        # Fallback to minimal built-ins if registry empty
        return [
            {
                "name": "calendar.create_event",
                "description": "Fallback calendar event creation tool (registry unavailable)",
                "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}, "start_time": {"type": "string"}}},
            }
        ]
    
    async def process_message(self, message: str, user, conversation, db: Session) -> str:
        """Process SMS command using LLM with MCP tool access"""
        
        if not self.llm_enabled:
            # Fallback to basic processing
            return await self._fallback_response(message, user)
        
        try:
            # Get team context
            team_context = await self._get_team_context(user, db)
            
            # Create LLM prompt with tool access
            system_prompt = self._create_system_prompt(user, team_context)
            user_prompt = self._create_user_prompt(message, user, conversation)
            
            logger.info(f"🧠 Processing with LLM: {message[:50]}...")
            
            # EXPLICIT DEBUG: Track what tools Claude will use
            logger.info(f"📋 [TOOL DEBUG] Available tools for Claude: {[tool['name'] for tool in self.available_tools]}")
            logger.info(f"📋 [TOOL DEBUG] For scheduling requests, Claude should use: check_calendar_conflicts -> create_calendar_event")
            
            # Implement retry logic for handling 529 errors
            max_retries = 3
            retry_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Call Claude with tool use capability
                    response = self.claude_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        temperature=0.1,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                        tools=self.available_tools
                    )
                    
                    logger.info(f"🤖 Claude response: {len(response.content)} content blocks")
                    
                    # Process Claude's response and tool calls
                    return await self._process_llm_response(response, user, db, message)
                    
                except Exception as e:
                    # Check if this is a 529 Overloaded error
                    error_str = str(e)
                    if "529" in error_str and "overloaded" in error_str.lower():
                        if attempt < max_retries - 1:  # Not the last attempt
                            logger.warning(f" Claude API 529 Overloaded error (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
                            import asyncio
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f" Claude API 529 Overloaded error after {max_retries} attempts")
                            return await self._fallback_response(message, user)
                    else:
                        # For other errors, don't retry
                        logger.error(f" Claude API call failed: {e}")
                        return await self._fallback_response(message, user)
            
        except Exception as e:
            logger.error(f"❌ LLM processing error: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return await self._fallback_response(message, user)
    
    def _create_system_prompt(self, team_member, team_context: Dict) -> str:
        """Create system prompt for Claude with natural conversation approach"""
        current_time = datetime.now()
        tomorrow = current_time + timedelta(days=1)
        
        # Using string concatenation to avoid f-string format specifier conflicts with JSON content
        return ("You are a smart, helpful family assistant who coordinates meetings via SMS. You have access to Google Calendar and can create real events.\n\n"
                "CONTEXT:\n"
                "- Today: " + current_time.strftime('%A, %B %d, %Y at %I:%M %p') + "\n"
                "- Tomorrow: " + tomorrow.strftime('%A, %B %d, %Y') + "\n"
                "- User: " + team_member.name + "\n"
                "- Family: " + ', '.join([m['name'] for m in team_context['members']]) + "\n\n"
                "YOUR PERSONALITY:\n"
                "- Conversational and natural (like texting a smart friend)\n"
                "- Ask clarifying questions when things are unclear\n"
                "- Make intelligent assumptions but confirm when important\n"
                "- Keep responses concise for SMS (under 160 chars when possible)\n"
                "- Use friendly emojis appropriately\n\n"
                "TOOLS AVAILABLE:\n"
                "- check_calendar_conflicts: Check if a time slot is free\n"
                "- create_calendar_event: Create calendar events with invites\n"
                "- find_calendar_free_time: Find available time slots\n"
                "- list_upcoming_events: See what's coming up\n\n"
                "IMPORTANT WORKFLOW - FOLLOW EXACTLY:\n"
                "1. For ANY scheduling request: You MUST call check_calendar_conflicts first\n"
                "2. If no conflicts found: You MUST immediately call create_calendar_event in the SAME response\n"
                "3. Use multiple tools in sequence - don't stop after just checking conflicts\n"
                "4. Tool results are for YOUR decision making, not messages to relay to the user\n"
                "5. Only respond to user AFTER you've completed all necessary tool calls\n\n"
                "CRITICAL RULE: When check_calendar_conflicts returns ready_to_create: true or suggested_action: create_event, you MUST immediately call create_calendar_event in the same response. DO NOT just respond to the user - create the event first!\n\n"
                "EXPLICIT EXAMPLE:\n"
                "User: Schedule meeting tomorrow at 3pm\n"
                "Step 1: Call check_calendar_conflicts\n"
                "Result: has_conflicts: false, ready_to_create: true\n"
                "Step 2: MUST call create_calendar_event immediately\n"
                "Result: success: true, event_id: ...\n"
                "Step 3: Then respond to user: Meeting scheduled!\n\n"
                "NEVER skip step 2 - always create the event when no conflicts are found!\n\n"
                "HOW TO BE SMART:\n"
                "- If someone says schedule dinner tomorrow at 7pm → you can reasonably assume it's a family dinner\n"
                "- If someone says schedule a work call → probably just for them\n"
                "- If unclear who should be invited, just ask: Should I invite the family or just you?\n"
                "- If you detect potential conflicts, mention it: I see you have X at that time, want to try Y instead?\n"
                "- Make events that make sense - don't overthink it\n\n"
                "BE NATURAL: Respond like a helpful human assistant would via text message. Ask questions when you need clarification. Make reasonable assumptions. Have a conversation!\n\n"
                "CORRECT TOOL WORKFLOW EXAMPLES:\n"
                "✅ User: Schedule lunch tomorrow at noon\n"
                "   Step 1: Call check_calendar_conflicts\n"
                "   Step 2: Call create_calendar_event (in same response)\n"
                "   Step 3: Respond: Lunch meeting created for tomorrow at noon! Here's your calendar link...\n\n"
                "❌ WRONG EXAMPLE:\n"
                "   Step 1: Call check_calendar_conflicts\n"
                "   Step 2: Respond: Time slot available! Should I create it? (MISSING create_calendar_event)\n\n"
                "❌ WRONG: Telling user about tool requirements instead of just using the tools")

    def _create_user_prompt(self, message_text: str, team_member, conversation=None) -> str:
        """Create user prompt with SMS context and conversation history"""
        
        # Build comprehensive conversation history
        conversation_context = ""
        pending_context = ""
        
        if conversation and conversation.context:
            # Include recent message history
            recent_messages = conversation.context.get("recent_messages", [])
            if recent_messages:
                conversation_context = "\n\n=== CONVERSATION HISTORY ==="
                # Show last 4 messages (excluding current one)
                history_messages = recent_messages[:-1] if len(recent_messages) > 1 else []
                
                if history_messages:
                    conversation_context += "\nRecent conversation context:\n"
                    for i, msg in enumerate(history_messages[-4:]):  # Last 4 messages
                        timestamp = msg.get("timestamp", "")
                        message_content = msg.get("message", "")
                        # Parse timestamp for relative time
                        try:
                            from datetime import datetime
                            msg_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_ago = datetime.utcnow() - msg_time.replace(tzinfo=None)
                            if time_ago.total_seconds() < 300:  # Less than 5 minutes
                                time_desc = "just now"
                            elif time_ago.total_seconds() < 3600:  # Less than 1 hour
                                mins = int(time_ago.total_seconds() / 60)
                                time_desc = f"{mins} min ago"
                            else:
                                time_desc = msg_time.strftime("%I:%M %p")
                        except:
                            time_desc = "recently"
                        
                        conversation_context += "  [" + time_desc + "] " + team_member.name + ": \"" + message_content + "\"\n"
                    conversation_context += "\n"
                    logger.info(f"📚 [CONTEXT] Including {len(history_messages)} previous messages")
            
            # Include pending confirmation state
            if "pending_confirmation" in conversation.context:
                pending = conversation.context["pending_confirmation"]
                pending_context = "\n=== PENDING CONFIRMATION ===\n"
                pending_context += "Type: " + pending.get('type', 'unknown') + "\n"
                
                if pending.get('type') == 'waiting_for_emails':
                    # Special handling for email waiting
                    event_details = pending.get('event_details', {})
                    unmapped_attendees = pending.get('unmapped_attendees', [])
                    pending_context += "Event: " + event_details.get('title', 'Meeting') + "\n"
                    pending_context += "Time: " + event_details.get('start_time', 'TBD') + "\n"
                    pending_context += "Waiting for email addresses for: " + ', '.join(unmapped_attendees) + "\n"
                    pending_context += "\nIMPORTANT: If the user's current message contains email addresses, extract them and create the calendar event with the stored event details plus the provided email addresses as attendees. Use create_calendar_event tool.\n"
                elif "details" in pending:
                    details = pending["details"]
                    pending_context += "Details: " + json.dumps(details, indent=2) + "\n"
                    
                pending_context += "\nThe user may be responding to this pending item.\n"
                logger.info(f"⏳ [PENDING] Found pending confirmation: {pending.get('type')}")
            
            # Include last detected intent
            if "last_intent" in conversation.context:
                last_intent = conversation.context["last_intent"]
                conversation_context += "Last detected intent: " + last_intent + "\n"
                logger.info(f"🎯 [INTENT] Previous intent: {last_intent}")
        
        # Create enhanced prompt with full context using string concatenation to avoid f-string conflicts
        base_prompt = ("CURRENT SMS from " + team_member.name + ": \"" + message_text + "\"" + 
                      conversation_context + pending_context + 
                      "\n\n=== YOUR ROLE ===\n"
                      "You are their helpful family assistant. You coordinate meetings via SMS and have access to calendar tools.\n\n"
                      "=== CONTEXT ANALYSIS ===\n"
                      "Analyze the conversation history above to understand:\n"
                      "1. What they're trying to accomplish\n"
                      "2. If this message is a follow-up/response to previous messages\n"
                      "3. If they're confirming something you asked about\n"
                      "4. What information is still needed\n\n"
                      "=== RESPONSE GUIDELINES ===\n"
                      "• If this continues a previous conversation, acknowledge what was discussed\n"
                      "• For scheduling: Use check_calendar_conflicts first, then create_calendar_event if clear\n"
                      "• For confirmations (\"yes\", \"sounds good\", etc.), refer to pending items\n"
                      "• Keep responses concise for SMS (under 160 chars when possible)\n"
                      "• Be conversational and natural\n"
                      "• Ask clarifying questions if needed\n\n"
                      "=== TOOL USAGE ===\n"
                      "For ANY scheduling request: check_calendar_conflicts → create_calendar_event (both in same response)\n"
                      "For questions about calendar: use list_upcoming_events\n"
                      "For finding free time: use find_calendar_free_time\n\n"
                      "IMPORTANT: Complete all necessary tool calls before responding to the user. Don't ask for permission to use tools - just use them.")
        
        return base_prompt

    async def _process_llm_response(self, response, team_member, db, message_text: str) -> str:
        """Process Claude's response and execute any tool calls"""
        
        tool_results = []
        final_text = ""
        
        # Process all content blocks
        tool_calls_made = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_calls_made.append(content_block.name)
                # Execute tool
                tool_name = content_block.name
                tool_input = content_block.input
                
                logger.info(f"🔧 Executing MCP tool: {tool_name} with input: {json.dumps(tool_input, indent=2)}")
                
                # CRITICAL DEBUG: Show what Claude chose for dates
                if tool_name == "create_calendar_event":
                    start_time_input = tool_input.get('start_time', 'NOT PROVIDED')
                    logger.info(f"😨 [CLAUDE DATE DEBUG] Claude chose start_time: '{start_time_input}'")
                    logger.info(f"😨 [CLAUDE DATE DEBUG] Original SMS message: '{message_text}'")
                    
                    # Check if Claude made the right choice
                    current_time = datetime.now()
                    tomorrow = current_time + timedelta(days=1)
                    logger.info(f"😨 [CLAUDE DATE DEBUG] Today is {current_time.strftime('%A %B %d, %Y')}")
                    logger.info(f"😨 [CLAUDE DATE DEBUG] Tomorrow should be {tomorrow.strftime('%A %B %d, %Y')}")
                    
                    if "tomorrow" in message_text.lower():
                        logger.info(f"😨 [CLAUDE DATE DEBUG] User said 'tomorrow' - Claude should pick {tomorrow.strftime('%Y-%m-%d')}")
                        if start_time_input and tomorrow.strftime('%Y-%m-%d') not in start_time_input:
                            logger.error(f"🐛 [CLAUDE BUG] Claude picked wrong date for 'tomorrow'!")
                            logger.error(f"🐛 Expected: {tomorrow.strftime('%Y-%m-%d')} ({tomorrow.strftime('%A')})")
                            logger.error(f"🐛 Claude chose: {start_time_input}")
                
                tool_result = await self._execute_mcp_tool(tool_name, tool_input, team_member, db, message_text)
                tool_results.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": tool_result
                })
                
            elif content_block.type == "text":
                final_text = content_block.text
        
        # EXPLICIT DEBUG: Show what tools Claude actually called
        logger.info(f"📋 [TOOL DEBUG] Tools Claude actually called: {tool_calls_made}")
        
        # Check if this was a scheduling request that should have created an event
        is_scheduling_request = any(word in message_text.lower() for word in ['schedule', 'meeting', 'event', 'lunch', 'dinner', 'call'])
        if is_scheduling_request:
            has_conflict_check = 'check_calendar_conflicts' in tool_calls_made
            has_event_creation = 'create_calendar_event' in tool_calls_made
            
            logger.info(f"📋 [SCHEDULING DEBUG] This appears to be a scheduling request: '{message_text}'")
            logger.info(f"📋 [SCHEDULING DEBUG] Conflict check called: {has_conflict_check}")
            logger.info(f"📋 [SCHEDULING DEBUG] Event creation called: {has_event_creation}")
            
            if has_conflict_check and not has_event_creation:
                logger.error(f"🚫 [TOOL ERROR] Claude checked conflicts but didn't create event! This is the bug!")
                logger.error(f"🚫 [TOOL ERROR] Expected: check_calendar_conflicts -> create_calendar_event")
                logger.error(f"🚫 [TOOL ERROR] Actual: {' -> '.join(tool_calls_made) if tool_calls_made else 'No tools called'}")
                
                # 🔧 RUNTIME WORKFLOW ENFORCEMENT: Force event creation when Claude misses it
                logger.warning(f"🔧 [WORKFLOW ENFORCEMENT] Automatically forcing event creation...")
                
                # Find the conflict check result to get the time details
                conflict_result = None
                for result in tool_results:
                    if result['tool'] == 'check_calendar_conflicts':
                        conflict_result = result['result']
                        break
                
                if conflict_result and not conflict_result.get('has_conflicts', True):
                    # Extract timing info from the original conflict check
                    last_conflict_input = None
                    for result in tool_results:
                        if result['tool'] == 'check_calendar_conflicts':
                            last_conflict_input = result['input']
                            break
                    
                    if last_conflict_input:
                        # Extract proper title from message instead of generic title
                        extracted_title = self._extract_meeting_title_from_message(message_text)
                        
                        # Force create the event with proper title
                        forced_event_input = {
                            "title": extracted_title,  # Use extracted subject
                            "start_time": last_conflict_input['start_time'],
                            "duration_minutes": last_conflict_input.get('duration_minutes', 60),
                            "description": f"Auto-created from: {message_text}"
                        }
                        
                        logger.info(f"🔧 [FORCED CREATION] Creating event with: {json.dumps(forced_event_input, indent=2)}")
                        
                        forced_result = await self._execute_mcp_tool("create_calendar_event", forced_event_input, team_member, db, message_text)
                        tool_results.append({
                            "tool": "create_calendar_event",
                            "input": forced_event_input,
                            "result": forced_result
                        })
                        
                        logger.info(f"✅ [FORCED CREATION] Event creation forced successfully: {forced_result.get('success', False)}")
        
        # If tools were used, get Claude's final response based on results
        if tool_results:
            # Check if any tool result requires asking for email addresses
            ask_for_emails_result = None
            for result in tool_results:
                if result['result'].get('ask_for_emails'):
                    ask_for_emails_result = result['result']
                    break
            
            if ask_for_emails_result:
                # Handle ask for emails case - return directly without calling Claude again
                unmapped = ask_for_emails_result.get('unmapped_attendees', [])
                event_details = ask_for_emails_result.get('event_details', {})
                
                logger.info(f"❓ Asking user for email addresses for: {unmapped}")
                
                # Store the pending event details for when user provides emails
                await self._store_pending_event_creation(team_member, message_text, event_details, unmapped, db)
                
                # Generate friendly response asking for emails
                title = event_details.get('title', 'meeting')
                time_str = event_details.get('start_time', '')
                
                if len(unmapped) == 1:
                    return f"I'll schedule '{title}' for {time_str}, but I couldn't find {unmapped[0]} in your team. Could you provide their email address so I can invite them?"
                else:
                    return f"I'll schedule '{title}' for {time_str}, but I couldn't find {', '.join(unmapped)} in your team. Could you provide their email addresses so I can invite them?"
            
            logger.info(f"🎯 Tool execution complete. Getting final response from Claude...")
            
            tool_summary = "\\n".join([
                f"{result['tool']}: {json.dumps(result['result'], default=str)}"
                for result in tool_results
            ])
            
            # 🔥 CONTEXT FIX: Include original message and full context in second Claude call
            # Using string concatenation to avoid f-string format specifier conflicts with JSON content
            context_prompt = ("ORIGINAL SMS REQUEST from " + team_member.name + ": \"" + message_text + "\""
                            "\n\nTOOL EXECUTION RESULTS:\n" + tool_summary + 
                            "\n\nPlease provide a helpful SMS response that:"
                            "\n1. Acknowledges what they originally asked for"
                            "\n2. Confirms what was accomplished"
                            "\n3. Includes relevant details (times, links, etc.)"
                            "\n4. Keeps it concise for SMS (under 160 chars when possible)"
                            "\n5. Uses a friendly, conversational tone"
                            "\n\nRemember: You just helped them with \"" + message_text + "\" - make sure your response connects back to their original request!")
            
            final_response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": context_prompt}
                ]
            )
            
            response_text = final_response.content[0].text
            
            # Store context for follow-up if response asks for confirmation
            if any(phrase in response_text.lower() for phrase in ['confirm', 'should i', 'would you like', 'ok?', 'sound good']):
                await self._store_pending_confirmation(team_member, message_text, tool_results, db)
            
            return response_text
        
        else:
            # Claude responded directly without tools
            response_text = final_text if final_text else "I'm here to help! Try asking me to schedule a meeting or check your calendar."
            
            # Check if Claude is asking for more information - store as pending
            if any(phrase in response_text.lower() for phrase in ['when', 'what time', 'who should', 'which']):
                await self._store_pending_question(team_member, message_text, response_text, db)
            
            return response_text
    
    async def _execute_mcp_tool(self, tool_name: str, tool_input: Dict, team_member, db, message_text: str) -> Dict:
        """Execute specific MCP tool and return results"""
        
        try:
            if tool_name == "create_calendar_event":
                return await self._tool_create_calendar_event(tool_input, team_member, db, message_text)
            
            elif tool_name == "check_calendar_conflicts":
                return await self._tool_check_conflicts(tool_input, team_member, db, message_text)
            
            elif tool_name == "find_calendar_free_time":
                return await self._tool_find_free_time(tool_input, team_member, db, message_text)
            
            elif tool_name == "list_upcoming_events":
                return await self._tool_list_events(tool_input, team_member, db, message_text)
            
            elif tool_name == "create_calendar_event_with_emails":
                return await self._tool_create_calendar_event_with_emails(tool_input, team_member, db, message_text)
            
            elif tool_name == "get_workout_context":
                return await self._tool_get_workout_context(tool_input, team_member, message_text)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def _store_pending_confirmation(self, team_member, original_message: str, tool_results: list, db):
        """Store pending confirmation state in conversation context."""
        try:
            from database.models import Conversation
                
            conversation = db.query(Conversation).filter(
                Conversation.phone_number == team_member.phone
            ).first()
                
            if conversation:
                if not conversation.context:
                    conversation.context = {}
                    
                # Store pending confirmation details
                conversation.context["pending_confirmation"] = {
                    "type": "tool_execution_confirmation",
                    "original_request": original_message,
                    "tool_results": tool_results,
                    "timestamp": datetime.utcnow().isoformat(),
                    "awaiting_response": True
                }
                    
                db.commit()
                logger.info(f"⏳ [PENDING] Stored pending confirmation for {team_member.name}")
        except Exception as e:
            logger.error(f"⚠️ [PENDING] Failed to store pending confirmation: {e}")
    
    async def _store_pending_event_creation(self, team_member, original_message: str, event_details: Dict, unmapped_attendees: List[str], db):
        """Store pending event creation when waiting for email addresses."""
        try:
            from database.models import Conversation
                
            conversation = db.query(Conversation).filter(
                Conversation.phone_number == team_member.phone
            ).first()
                
            if conversation:
                if not conversation.context:
                    conversation.context = {}
                    
                # Store pending event creation details
                conversation.context["pending_confirmation"] = {
                    "type": "waiting_for_emails",
                    "original_request": original_message,
                    "event_details": event_details,
                    "unmapped_attendees": unmapped_attendees,
                    "timestamp": datetime.utcnow().isoformat(),
                    "awaiting_response": True
                }
                    
                db.commit()
                logger.info(f"✉️ [PENDING] Stored pending event creation waiting for emails: {unmapped_attendees}")
        except Exception as e:
            logger.error(f"⚠️ [PENDING] Failed to store pending event creation: {e}")
    
    async def _store_pending_question(self, team_member, original_message: str, question_response: str, db):
        """Store pending question state in conversation context."""
        try:
            from database.models import Conversation
                
            conversation = db.query(Conversation).filter(
                Conversation.phone_number == team_member.phone
            ).first()
                
            if conversation:
                if not conversation.context:
                    conversation.context = {}
                    
                # Store pending question details
                conversation.context["pending_confirmation"] = {
                    "type": "clarification_question",
                    "original_request": original_message,
                    "question_asked": question_response,
                    "timestamp": datetime.utcnow().isoformat(),
                    "awaiting_response": True
                }
                    
                db.commit()
                logger.info(f"❓ [PENDING] Stored pending question for {team_member.name}")
        except Exception as e:
            logger.error(f"⚠️ [PENDING] Failed to store pending question: {e}")
    
    async def _tool_check_conflicts(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
        """Check for calendar conflicts at proposed time - SAFE VERSION"""
        
        try:
            start_time_str = input_data["start_time"]
            duration_minutes = input_data.get("duration_minutes", 60)
            
            # Parse the proposed time
            start_time = self._parse_datetime_bulletproof(start_time_str, message_text)
            
            if not start_time:
                logger.warning(f"⚠️ Could not parse time: {start_time_str} - returning no conflicts")
                return {
                    "has_conflicts": False,
                    "message": "Unable to check conflicts, but proceeding",
                    "suggested_action": "create_event"
                }
            
            logger.info(f"🔍 CONFLICT CHECK: {start_time.strftime('%A, %B %d at %I:%M %p')}")
            
            # Check if calendar client has the check_conflicts method
            if not hasattr(self.calendar_client, 'check_conflicts'):
                logger.warning("⚠️ Calendar client doesn't support conflict checking - skipping")
                return {
                    "has_conflicts": False,
                    "message": "Conflict checking not available",
                    "suggested_action": "create_event"
                }
            
            # Check for conflicts using calendar client
            conflict_result = await self.calendar_client.check_conflicts(
                start_time=start_time,
                duration_minutes=duration_minutes
            )
            
            if conflict_result.get("has_conflicts"):
                conflicts = conflict_result.get("conflicts", [])
                conflict_titles = [c.get("title", "Unknown") for c in conflicts]
                
                logger.warning(f"⚠️ CONFLICTS DETECTED: {', '.join(conflict_titles)}")
                
                return {
                    "has_conflicts": True,
                    "conflicts": conflicts,
                    "message": f"Conflict detected with: {', '.join(conflict_titles)}",
                    "suggested_action": "find_alternative_time"
                }
            else:
                logger.info(f"✅ NO CONFLICTS - time slot available")
                return {
                    "has_conflicts": False,
                    "message": "Time slot is available",
                    "suggested_action": "create_event",
                    "claude_instruction": "You must now call create_calendar_event tool to complete this scheduling request",
                    "ready_to_create": True
                }
                
        except Exception as e:
            logger.error(f"❌ Conflict check failed: {str(e)} - defaulting to no conflicts")
            # SAFE FALLBACK: Don't fail, just proceed without conflict detection
            return {
                "has_conflicts": False,
                "message": "Conflict check failed, proceeding anyway",
                "suggested_action": "create_event",
                "error_note": str(e)
            }
    
    async def _tool_get_workout_context(self, input_data: Dict, team_member, message_text: str) -> Dict:
        """Get workout context for smart scheduling"""
        
        try:
            proposed_time_str = input_data.get("proposed_time")
            limit = input_data.get("limit", 7)
            
            # Initialize Strava client if not already done - SAFELY
            if not self.strava_client:
                try:
                    from strava_integrations.strava_client import StravaClient
                    self.strava_client = StravaClient()
                    logger.info("✅ Strava client initialized")
                except ImportError as e:
                    logger.warning(f"⚠️ Strava integration not available: {e}")
                    # Return mock workout data instead of failing
                    return {
                        "success": True,
                        "recent_activities_count": 3,
                        "workout_patterns": {"recommendations": ["No recent workout data - using mock analysis"]},
                        "proximity_analysis": {"recommendation": "Strava integration not configured"},
                        "recommendations": ["Consider setting up Strava integration for workout-aware scheduling"],
                        "optimal_meeting_times": ["Morning: 9-11am", "Afternoon: 2-4pm", "Evening: 6-8pm"]
                    }
                except Exception as e:
                    logger.error(f"❌ Error initializing Strava client: {e}")
                    return {"error": f"Strava initialization failed: {str(e)}"}
            
            # Get recent activities
            activities = await self.strava_client.get_athlete_activities(limit=limit)
            
            # Analyze workout patterns
            analysis = self.strava_client.analyze_workout_patterns(activities)
            
            # If proposed time provided, check proximity to workouts
            proximity_analysis = None
            if proposed_time_str:
                try:
                    proposed_time = self._parse_datetime_bulletproof(proposed_time_str, message_text)
                    if proposed_time:
                        proximity_analysis = self._analyze_workout_proximity(activities, proposed_time)
                except Exception as e:
                    logger.warning(f"Could not analyze workout proximity: {e}")
            
            logger.info(f"💪 WORKOUT CONTEXT: {len(activities)} recent activities analyzed")
            
            return {
                "success": True,
                "recent_activities_count": len(activities),
                "workout_patterns": analysis,
                "proximity_analysis": proximity_analysis,
                "recommendations": analysis.get("recommendations", []),
                "optimal_meeting_times": analysis.get("optimal_meeting_times", [])
            }
            
        except Exception as e:
            logger.error(f"❌ Workout context error: {str(e)}")
            # Return safe fallback instead of failing completely
            return {
                "success": False,
                "error": f"Workout analysis failed: {str(e)}",
                "fallback_recommendations": ["Schedule meetings during typical business hours"],
                "note": "Workout integration temporarily unavailable"
            }
    
    def _analyze_workout_proximity(self, activities: List[Dict], proposed_time: datetime) -> Dict:
        """Analyze how close proposed meeting is to recent workouts"""
        
        if not activities:
            return {"recommendation": "No recent workout data"}
        
        close_workouts = []
        
        for activity in activities:
            try:
                activity_time = datetime.fromisoformat(activity["start_date"].replace('Z', '+00:00'))
                time_diff = abs((proposed_time - activity_time).total_seconds() / 3600)  # Hours
                
                if time_diff < 24:  # Within 24 hours
                    intensity = "high" if activity.get("average_heartrate", 0) > 150 else "moderate"
                    close_workouts.append({
                        "activity": activity["name"],
                        "type": activity["type"],
                        "time_diff_hours": round(time_diff, 1),
                        "intensity": intensity
                    })
                    
            except Exception as e:
                logger.warning(f"Error analyzing activity: {e}")
        
        if close_workouts:
            high_intensity_close = any(w["intensity"] == "high" and w["time_diff_hours"] < 2 for w in close_workouts)
            
            if high_intensity_close:
                return {
                    "warning": "High intensity workout within 2 hours",
                    "recommendation": "Consider scheduling 2+ hours after intense workouts",
                    "close_workouts": close_workouts
                }
            else:
                return {
                    "info": "Recent workouts detected but timing looks good",
                    "close_workouts": close_workouts
                }
        
        return {"recommendation": "No workout conflicts detected"}
    
    async def _tool_create_calendar_event(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
        """Create calendar event using MCP calendar client"""
        
        try:
            # Parse start time - handle various formats
            start_time_str = input_data["start_time"]
            
            # BULLETPROOF DATE OVERRIDE: If user said "tomorrow" but Claude picked wrong date, fix it!
            if "tomorrow" in message_text.lower():
                current_time = datetime.now()
                tomorrow = current_time + timedelta(days=1)
                expected_date = tomorrow.strftime('%Y-%m-%d')
                
                logger.info(f"🛡️ [DATE OVERRIDE] User said 'tomorrow', forcing date to {expected_date} ({tomorrow.strftime('%A')})")
                
                # Extract time from Claude's choice, but force the date to be tomorrow
                time_part = "19:00"  # Default 7 PM
                if start_time_str:
                    # Try to extract time from Claude's input
                    import re
                    time_match = re.search(r'T(\d{2}:\d{2})', start_time_str)
                    if time_match:
                        time_part = time_match.group(1)
                    elif "lunch" in message_text.lower():
                        time_part = "13:00"  # 1 PM for lunch
                    elif "dinner" in message_text.lower():
                        time_part = "18:00"  # 6 PM for dinner
                    elif "breakfast" in message_text.lower():
                        time_part = "09:00"  # 9 AM for breakfast
                
                # Force tomorrow's date with extracted time
                corrected_start_time_str = f"{expected_date}T{time_part}:00"
                logger.info(f"🛡️ [DATE OVERRIDE] Corrected start_time: {corrected_start_time_str}")
                start_time_str = corrected_start_time_str
            
            start_time = self._parse_datetime_bulletproof(start_time_str, message_text)
            
            logger.info(f"🗓️ CALENDAR EVENT CREATION ATTEMPT:")
            logger.info(f"   Title: {input_data['title']}")
            logger.info(f"   Start time: {start_time}")
            logger.info(f"   Duration: {input_data.get('duration_minutes', 60)} minutes")
            
            if not start_time:
                logger.error(f"❌ Could not parse start time: {start_time_str}")
                return {"error": f"Could not parse start time: {start_time_str}"}
            
            # Get team members for attendees
            from database.models import Team, TeamMember
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
            
            logger.info(f"👥 Team members found: {len(team_members)}")
            for member in team_members:
                logger.info(f"   - {member.name} ({member.phone})")
            
            # Create Google Meet link
            logger.info(f"🔗 Creating Google Meet link...")
            meet_link = await self.meet_client.create_meeting(input_data["title"])
            logger.info(f"✅ Meet link created: {meet_link}")
            
            # Create calendar event - THIS IS THE KEY STEP
            logger.info(f"📅 Creating calendar event via calendar client...")
            
            # Get team members for potential attendees
            all_family_emails = [member.email for member in team_members if member.email and member.phone != team_member.phone]
            
            # Default to no attendees (individual event)
            attendee_emails = []
            
            # Use attendees passed from the tool input (Claude decides who to invite)
            if "attendees" in input_data and input_data["attendees"]:
                # Claude specified specific attendees - use those
                specified_attendees = input_data["attendees"]
                logger.info(f"👥 Claude specified attendees: {specified_attendees}")
                
                # Enhanced name mapping with fuzzy matching
                mapped_members = []
                unmapped_attendees = []
                
                for attendee in specified_attendees:
                    attendee_found = False
                    attendee_lower = attendee.lower().strip()
                    
                    # Try to find matching family member with multiple strategies
                    for member in team_members:
                        member_name_lower = member.name.lower().strip()
                        
                        # Strategy 1: Exact name match
                        if member_name_lower == attendee_lower:
                            if member.email and member.phone != team_member.phone:
                                attendee_emails.append(member.email)
                                mapped_members.append(f"{member.name} ({member.email})")
                                attendee_found = True
                                break
                        
                        # Strategy 2: First name match (e.g., "Rick" matches "Rick Smith")
                        elif ' ' in member_name_lower and attendee_lower in member_name_lower:
                            if member.email and member.phone != team_member.phone:
                                attendee_emails.append(member.email)
                                mapped_members.append(f"{member.name} ({member.email})")
                                attendee_found = True
                                break
                        
                        # Strategy 3: Partial match (e.g., "Hari" matches "Hari Thangavel")
                        elif attendee_lower in member_name_lower or member_name_lower in attendee_lower:
                            if member.email and member.phone != team_member.phone:
                                attendee_emails.append(member.email)
                                mapped_members.append(f"{member.name} ({member.email})")
                                attendee_found = True
                                break
                    
                    if not attendee_found:
                        unmapped_attendees.append(attendee)
                
                logger.info(f"📧 Mapped to emails: {attendee_emails}")
                logger.info(f"✅ Successfully mapped: {mapped_members}")
                
                if unmapped_attendees:
                    logger.warning(f"⚠️ Could not find team members: {unmapped_attendees}")
                    logger.warning(f"💡 Available team members: {[m.name for m in team_members]}")
                    
                    # Store unmapped attendees for the response - LLM should ask for emails
                    input_data["_unmapped_attendees"] = unmapped_attendees
                    input_data["_available_members"] = [m.name for m in team_members]
                    input_data["_should_ask_for_emails"] = True
            else:
                logger.info(f"👤 No attendees specified - creating individual event")
            
            # Check if we need to ask for email addresses before creating the event
            if input_data.get("_should_ask_for_emails"):
                unmapped = input_data.get("_unmapped_attendees", [])
                available = input_data.get("_available_members", [])
                
                logger.info(f"❓ Need to ask for email addresses for: {unmapped}")
                
                return {
                    "success": False,
                    "ask_for_emails": True,
                    "unmapped_attendees": unmapped,
                    "available_members": available,
                    "message": f"I couldn't find {', '.join(unmapped)} in your team. Could you provide their email address(es) so I can invite them?",
                    "suggested_action": "ask_for_emails",
                    "event_details": {
                        "title": input_data["title"],
                        "start_time": start_time.strftime("%A, %B %d at %I:%M %p"),
                        "duration_minutes": input_data.get("duration_minutes", 60)
                    }
                }
            
            # Log attendee decision
            if attendee_emails:
                logger.info(f"👥 Event will include {len(attendee_emails)} attendees: {', '.join(attendee_emails)}")
            else:
                logger.info(f"👤 Individual event - no attendees")
            
            # Debug: Show all team members
            for member in team_members:
                invited = "✅ INVITED" if (member.email and member.email in attendee_emails) else "❌ Not invited"
                logger.info(f"👤 {member.name} ({member.phone}) - {invited}")
            
            event = await self.calendar_client.create_event(
                title=input_data["title"],
                start_time=start_time,
                duration_minutes=input_data.get("duration_minutes", 60),
                attendees=attendee_emails,
                meet_link=meet_link
            )
            
            logger.info(f"📊 Calendar client response: {event}")
            
            if event:
                logger.info(f"✅ Calendar event created successfully")
                logger.info(f"   Event ID: {event.get('id')}")
                logger.info(f"   Source: {event.get('source', 'unknown')}")
                
                # Save to database
                from database.models import Meeting
                meeting = Meeting(
                    team_id=team_member.team_id,
                    title=input_data["title"],
                    scheduled_time=start_time,
                    google_meet_link=meet_link,
                    google_calendar_event_id=event.get("id"),
                    created_by_phone=team_member.phone,
                    description=input_data.get("description", "")
                )
                db.add(meeting)
                db.commit()
                
                logger.info(f"💾 Meeting saved to database with ID: {meeting.id}")
                
                return {
                    "success": True,
                    "event_id": event.get("id"),
                    "title": input_data["title"],
                    "start_time": start_time.strftime("%A, %B %d at %I:%M %p"),
                    "meet_link": meet_link,
                    "attendees_count": len(team_members),
                    "calendar_source": event.get("source", "unknown"),
                    "real_calendar_event": event.get("source") != "mock"
                }
            else:
                logger.error(f"❌ Calendar client returned None/False")
                return {"success": False, "error": "Calendar client failed to create event"}
            
        except Exception as e:
            logger.error(f"❌ Calendar event creation failed: {str(e)}", exc_info=True)
            return {"error": f"Calendar event creation failed: {str(e)}"}
    
    async def _tool_create_calendar_event_with_emails(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
        """Create calendar event when user provides email addresses for unknown attendees"""
        
        try:
            # Get pending event details from conversation context
            from database.models import Conversation
            
            conversation = db.query(Conversation).filter(
                Conversation.phone_number == team_member.phone
            ).first()
            
            if not conversation or not conversation.context.get("pending_confirmation"):
                return {"error": "No pending event found. Please start a new scheduling request."}
            
            pending = conversation.context["pending_confirmation"]
            
            if pending.get('type') != 'waiting_for_emails':
                return {"error": "No pending email request found."}
            
            # Get the stored event details
            event_details = pending.get('event_details', {})
            unmapped_attendees = pending.get('unmapped_attendees', [])
            provided_emails = input_data.get('provided_emails', [])
            
            # Use event details from pending or input
            title = input_data.get('title') or event_details.get('title', 'Meeting')
            start_time_str = input_data.get('start_time') or event_details.get('start_time')
            duration_minutes = input_data.get('duration_minutes', event_details.get('duration_minutes', 60))
            
            logger.info(f"✉️ Creating event with provided emails: {provided_emails}")
            logger.info(f"📅 Event details: {title} at {start_time_str}")
            
            # Parse the time
            start_time = self._parse_datetime_bulletproof(start_time_str, message_text)
            if not start_time:
                return {"error": f"Could not parse start time: {start_time_str}"}
            
            # Get team members
            from database.models import Team, TeamMember
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
            
            # Create Google Meet link
            logger.info(f"🔗 Creating Google Meet link...")
            meet_link = await self.meet_client.create_meeting(title)
            logger.info(f"✅ Meet link created: {meet_link}")
            
            # Build attendee list: existing team members + provided emails
            attendee_emails = []
            
            # Add existing team members (excluding the creator)
            for member in team_members:
                if member.email and member.phone != team_member.phone:
                    attendee_emails.append(member.email)
            
            # Add provided emails
            for email in provided_emails:
                if email and '@' in email and email not in attendee_emails:
                    attendee_emails.append(email.strip())
            
            logger.info(f"📧 Final attendee list: {attendee_emails}")
            
            # Create the calendar event
            event = await self.calendar_client.create_event(
                title=title,
                start_time=start_time,
                duration_minutes=duration_minutes,
                attendees=attendee_emails,
                meet_link=meet_link
            )
            
            if event:
                logger.info(f"✅ Calendar event created successfully with provided emails")
                
                # Save to database
                from database.models import Meeting
                meeting = Meeting(
                    team_id=team_member.team_id,
                    title=title,
                    scheduled_time=start_time,
                    google_meet_link=meet_link,
                    google_calendar_event_id=event.get("id"),
                    created_by_phone=team_member.phone,
                    description=input_data.get("description", "")
                )
                db.add(meeting)
                db.commit()
                
                # Clear the pending confirmation
                conversation.context["pending_confirmation"] = None
                db.commit()
                
                logger.info(f"💾 Meeting saved and pending confirmation cleared")
                
                return {
                    "success": True,
                    "event_id": event.get("id"),
                    "title": title,
                    "start_time": start_time.strftime("%A, %B %d at %I:%M %p"),
                    "meet_link": meet_link,
                    "attendees_invited": len(attendee_emails),
                    "provided_emails": provided_emails,
                    "calendar_source": event.get("source", "unknown"),
                    "real_calendar_event": event.get("source") != "mock"
                }
            else:
                return {"error": "Failed to create calendar event"}
                
        except Exception as e:
            logger.error(f"❌ Error creating event with provided emails: {str(e)}", exc_info=True)
            return {"error": f"Failed to create event: {str(e)}"}
    
    async def _tool_list_events(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
        """List upcoming events from both database and Google Calendar with proper timezone handling"""
        
        try:
            from database.models import Meeting
            from datetime import timezone as dt_timezone
            import pytz
            
            days_ahead = input_data.get("days_ahead", 7)
            limit = input_data.get("limit", 5)
            
            logger.info(f"📋 LISTING EVENTS: Looking {days_ahead} days ahead, limit {limit}")
            
            # Get events from Google Calendar first (more authoritative)
            calendar_events = []
            try:
                if hasattr(self.calendar_client, 'list_events'):
                    calendar_events = await self.calendar_client.list_events(
                        days_ahead=days_ahead, 
                        limit=limit
                    )
                    logger.info(f"📅 Retrieved {len(calendar_events)} events from Google Calendar")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get Google Calendar events: {e}")
            
            # Also get events from database as backup
            end_date = datetime.now() + timedelta(days=days_ahead)
            db_meetings = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > datetime.now(),
                Meeting.scheduled_time <= end_date
            ).order_by(Meeting.scheduled_time).limit(limit).all()
            
            logger.info(f"💾 Retrieved {len(db_meetings)} events from database")
            
            # Process and format events
            events = []
            
            # Process Google Calendar events with proper timezone handling
            for event in calendar_events:
                try:
                    start_time_str = event.get("start_time", "")
                    title = event.get("title", "No title")
                    
                    # Parse the Google Calendar datetime
                    if start_time_str:
                        try:
                            # Handle different formats from Google Calendar
                            if 'T' in start_time_str:
                                # ISO format: "2025-08-26T15:00:00-04:00" or "2025-08-26T15:00:00Z"
                                if start_time_str.endswith('Z'):
                                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                else:
                                    start_time = datetime.fromisoformat(start_time_str)
                                
                                # Convert to ET for display consistency
                                et_tz = pytz.timezone('US/Eastern')
                                if start_time.tzinfo is None:
                                    start_time = start_time.replace(tzinfo=pytz.UTC)
                                start_time_et = start_time.astimezone(et_tz)
                                
                                formatted_time = start_time_et.strftime("%A, %B %d at %I:%M %p ET")
                                logger.info(f"📅 Formatted Google Calendar event: {title} at {formatted_time}")
                                
                                events.append({
                                    "title": title,
                                    "start_time": formatted_time,
                                    "meet_link": event.get("meet_link"),
                                    "source": "google_calendar"
                                })
                            else:
                                # Date only format
                                events.append({
                                    "title": title,
                                    "start_time": start_time_str,
                                    "meet_link": event.get("meet_link"),
                                    "source": "google_calendar"
                                })
                        except Exception as parse_error:
                            logger.warning(f"⚠️ Failed to parse event time '{start_time_str}': {parse_error}")
                            events.append({
                                "title": title,
                                "start_time": start_time_str,  # Use raw string as fallback
                                "meet_link": event.get("meet_link"),
                                "source": "google_calendar"
                            })
                    else:
                        events.append({
                            "title": title,
                            "start_time": "Time not specified",
                            "meet_link": event.get("meet_link"),
                            "source": "google_calendar"
                        })
                        
                except Exception as event_error:
                    logger.error(f"❌ Error processing calendar event: {event_error}")
            
            # Process database events (as backup/supplement)
            for meeting in db_meetings:
                try:
                    # Handle timezone-aware datetime from database
                    scheduled_time = meeting.scheduled_time
                    
                    if scheduled_time:
                        if scheduled_time.tzinfo is None:
                            # Assume UTC if no timezone info
                            scheduled_time = scheduled_time.replace(tzinfo=pytz.UTC)
                        
                        # Convert to ET for display consistency
                        et_tz = pytz.timezone('US/Eastern')
                        scheduled_time_et = scheduled_time.astimezone(et_tz)
                        formatted_time = scheduled_time_et.strftime("%A, %B %d at %I:%M %p ET")
                        
                        # Check if this event is already in the Google Calendar list
                        already_listed = any(
                            e["title"] == meeting.title and 
                            e["source"] == "google_calendar" 
                            for e in events
                        )
                        
                        if not already_listed:
                            events.append({
                                "title": meeting.title,
                                "start_time": formatted_time,
                                "meet_link": meeting.google_meet_link,
                                "source": "database"
                            })
                            logger.info(f"📊 Added database event: {meeting.title} at {formatted_time}")
                        else:
                            logger.info(f"📋 Skipped duplicate: {meeting.title} (already in Google Calendar)")
                            
                except Exception as db_error:
                    logger.error(f"❌ Error processing database meeting: {db_error}")
            
            # Sort events by start time (best effort)
            events.sort(key=lambda x: x.get("start_time", "zzz"))
            
            if not events:
                return {"success": True, "events": [], "message": "No upcoming meetings"}
            
            logger.info(f"✅ Final event list: {len(events)} events total")
            for i, event in enumerate(events):
                logger.info(f"  {i+1}. {event['title']} - {event['start_time']} ({event['source']})")
            
            return {
                "success": True,
                "events": events,
                "count": len(events)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to list events: {str(e)}", exc_info=True)
            return {"error": f"Failed to list events: {str(e)}"}
    
    async def _tool_find_free_time(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
        """Find free time using enhanced calendar client"""
        
        try:
            duration_minutes = input_data.get("duration_minutes", 60)
            days_ahead = input_data.get("days_ahead", 7)
            preferred_hours = input_data.get("preferred_hours")
            
            logger.info(f"🔍 FINDING FREE TIME: {duration_minutes} min slots over {days_ahead} days")
            
            # Use the enhanced find_free_time method
            suggested_time = await self.calendar_client.find_free_time(
                duration_minutes=duration_minutes,
                days_ahead=days_ahead,
                preferred_hours=preferred_hours
            )
            
            if suggested_time:
                logger.info(f"✅ FOUND FREE TIME: {suggested_time.strftime('%A, %B %d at %I:%M %p')}")
                
                # Also provide a few alternative times
                alternatives = []
                for hour_offset in [1, 2, 24]:  # 1 hour later, 2 hours later, next day same time
                    alt_time = suggested_time + timedelta(hours=hour_offset)
                    alt_check = await self.calendar_client.check_conflicts(alt_time, duration_minutes)
                    if not alt_check["has_conflicts"]:
                        alternatives.append(alt_time.strftime("%A, %B %d at %I:%M %p"))
                        if len(alternatives) >= 2:  # Limit to 2 alternatives
                            break
                
                return {
                    "success": True,
                    "suggested_time": suggested_time.strftime("%A, %B %d at %I:%M %p"),
                    "suggested_time_iso": suggested_time.isoformat(),
                    "alternatives": alternatives,
                    "duration_minutes": duration_minutes,
                    "message": f"Available: {suggested_time.strftime('%A, %B %d at %I:%M %p')}"
                }
            else:
                logger.warning(f"⚠️ NO FREE TIME found in {days_ahead} days")
                
                # Suggest extending the search
                return {
                    "success": False,
                    "message": f"No {duration_minutes}-minute slots available in next {days_ahead} days",
                    "suggestion": "Try shorter duration or extend search to next week"
                }
                
        except Exception as e:
            logger.error(f"❌ Free time search failed: {str(e)}")
            return {"error": f"Failed to find free time: {str(e)}"}
    

    
    def _parse_datetime_bulletproof(self, time_str: str, original_message: str) -> Optional[datetime]:
        """
        BULLETPROOF DATE PARSING - FIXED VERSION
        Simple, reliable, and debuggable
        """
        
        logger.info(f"🛡️ [BULLETPROOF PARSER] Input: '{time_str}' from message: '{original_message}'")
        
        # Get current time once and use it consistently
        now = datetime.now()
        logger.info(f"🛡️ [BULLETPROOF PARSER] Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}")
        
        try:
            # STEP 1: Handle ISO datetime formats first
            if time_str and ('T' in time_str or '+' in time_str or 'Z' in time_str):
                try:
                    result = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    logger.info(f"✅ [BULLETPROOF PARSER] Parsed ISO format: {result}")
                    return result
                except:
                    logger.warning(f"⚠️ [BULLETPROOF PARSER] Failed to parse ISO format: {time_str}")
            
            # STEP 2: Parse natural language from ORIGINAL MESSAGE (more reliable)
            message_lower = original_message.lower()
            logger.info(f"🔍 [BULLETPROOF PARSER] Analyzing original message: '{message_lower}'")
            
            # STEP 3: Determine target date using simple, foolproof logic
            from datetime import timezone as dt_timezone
            import time
            
            # Get current time in local timezone
            now = datetime.now()
            
            if "tomorrow" in message_lower:
                target_date = (now + timedelta(days=1)).date()
                logger.info(f"📅 [BULLETPROOF PARSER] TOMORROW detected: {target_date} ({target_date.strftime('%A')})")
                
            elif "today" in message_lower:
                target_date = now.date()
                logger.info(f"📅 [BULLETPROOF PARSER] TODAY detected: {target_date} ({target_date.strftime('%A')})")
                
            elif "this weekend" in message_lower or "weekend" in message_lower:
                # Next Saturday
                days_until_saturday = (5 - now.weekday()) % 7
                if days_until_saturday == 0:  # It's Saturday
                    days_until_saturday = 7  # Next Saturday
                target_date = (now + timedelta(days=days_until_saturday)).date()
                logger.info(f"📅 [BULLETPROOF PARSER] WEEKEND detected: {target_date} ({target_date.strftime('%A')})")
                
            elif "next week" in message_lower:
                # Next Monday
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:  # It's Monday
                    days_until_monday = 7  # Next Monday
                target_date = (now + timedelta(days=days_until_monday)).date()
                logger.info(f"📅 [BULLETPROOF PARSER] NEXT WEEK detected: {target_date} ({target_date.strftime('%A')})")
                
            else:
                # Check for specific weekdays
                weekdays = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6
                }
                
                target_date = None
                for day_name, day_num in weekdays.items():
                    if day_name in message_lower:
                        days_ahead = (day_num - now.weekday()) % 7
                        if days_ahead == 0:  # Same day
                            days_ahead = 7  # Next week
                        target_date = (now + timedelta(days=days_ahead)).date()
                        logger.info(f"📅 [BULLETPROOF PARSER] {day_name.upper()} detected: {target_date} ({target_date.strftime('%A')})")
                        break
                
                if not target_date:
                    # Default fallback: tomorrow
                    target_date = (now + timedelta(days=1)).date()
                    logger.info(f"📅 [BULLETPROOF PARSER] NO DATE FOUND - defaulting to tomorrow: {target_date} ({target_date.strftime('%A')})")
            
            # STEP 4: Determine time using simple patterns with timezone awareness
            target_hour = 19  # Default 7 PM
            target_minute = 0
            target_timezone = None  # Will be set based on timezone indicators
            
            # Look for timezone indicators first
            from datetime import timezone as dt_timezone
            import time
            
            if 'et' in message_lower or 'eastern' in message_lower:
                # Eastern Time (UTC-5 in winter, UTC-4 in summer)
                target_timezone = dt_timezone(timedelta(hours=-5))  # Simplified to EST
                logger.info(f"🌍 [BULLETPROOF PARSER] EASTERN TIME detected")
            elif 'pt' in message_lower or 'pacific' in message_lower:
                target_timezone = dt_timezone(timedelta(hours=-8))  # PST
                logger.info(f"🌍 [BULLETPROOF PARSER] PACIFIC TIME detected")
            elif 'ct' in message_lower or 'central' in message_lower:
                target_timezone = dt_timezone(timedelta(hours=-6))  # CST
                logger.info(f"🌍 [BULLETPROOF PARSER] CENTRAL TIME detected")
            elif 'mt' in message_lower or 'mountain' in message_lower:
                target_timezone = dt_timezone(timedelta(hours=-7))  # MST
                logger.info(f"🌍 [BULLETPROOF PARSER] MOUNTAIN TIME detected")
            else:
                # Use local timezone
                local_offset = time.timezone if not time.daylight else time.altzone
                local_tz_offset = timedelta(seconds=-local_offset)
                target_timezone = dt_timezone(local_tz_offset)
                logger.info(f"🌍 [BULLETPROOF PARSER] Using local timezone: {local_tz_offset}")
            
            # Look for time indicators in original message (with timezone tolerance)
            time_patterns = [
                (r'(\d{1,2}):(\d{2})\s*(am|pm)(?:\s+(?:et|pt|ct|mt|eastern|pacific|central|mountain))?', 'hour_minute_ampm'),  # 2:30pm ET
                (r'(\d{1,2})\s*(am|pm)(?:\s+(?:et|pt|ct|mt|eastern|pacific|central|mountain))?', 'hour_ampm'),              # 4pm ET
                (r'(\d{1,2}):(\d{2})(?:\s+(?:et|pt|ct|mt|eastern|pacific|central|mountain))?', 'hour_minute_24h'),          # 14:30 ET
                (r'(\d{1,2})\s*pm(?:\s+(?:et|pt|ct|mt|eastern|pacific|central|mountain))?', 'hour_pm'),                    # 4pm ET (fallback)
                (r'(\d{1,2})\s*am(?:\s+(?:et|pt|ct|mt|eastern|pacific|central|mountain))?', 'hour_am'),                    # 9am ET (fallback)
            ]
            
            time_found = False
            logger.info(f"🔍 [TIME DEBUG] Looking for time patterns in: '{message_lower}'")
            for pattern, pattern_type in time_patterns:
                match = re.search(pattern, message_lower)
                logger.info(f"🔍 [TIME DEBUG] Testing pattern '{pattern}' ({pattern_type}): {match.group(0) if match else 'No match'}")
                if match:
                    logger.info(f"🎯 [TIME DEBUG] MATCH FOUND! Pattern: {pattern_type}, Groups: {match.groups()}")
                    if pattern_type == 'hour_minute_ampm':
                        hour = int(match.group(1))
                        minute = int(match.group(2))
                        ampm = match.group(3)
                        if ampm == 'pm' and hour != 12:
                            hour += 12
                        elif ampm == 'am' and hour == 12:
                            hour = 0
                        target_hour, target_minute = hour, minute
                        
                    elif pattern_type == 'hour_ampm':
                        hour = int(match.group(1))
                        ampm = match.group(2)
                        if ampm == 'pm' and hour != 12:
                            hour += 12
                        elif ampm == 'am' and hour == 12:
                            hour = 0
                        target_hour = hour
                        
                    elif pattern_type == 'hour_minute_24h':
                        target_hour = int(match.group(1))
                        target_minute = int(match.group(2))
                        
                    elif pattern_type in ['hour_pm', 'hour_am']:
                        hour = int(match.group(1))
                        if pattern_type == 'hour_pm' and hour != 12:
                            hour += 12
                        elif pattern_type == 'hour_am' and hour == 12:
                            hour = 0
                        target_hour = hour
                    
                    time_found = True
                    logger.info(f"🕐 [BULLETPROOF PARSER] TIME found: {target_hour:02d}:{target_minute:02d} from '{match.group(0)}'")
                    break
            
            if not time_found:
                # Look for time words
                if any(word in message_lower for word in ['morning', 'breakfast']):
                    target_hour = 9
                    logger.info(f"🌅 [BULLETPROOF PARSER] MORNING detected: 9:00 AM")
                elif any(word in message_lower for word in ['lunch', 'noon']):
                    target_hour = 12
                    logger.info(f"☀️ [BULLETPROOF PARSER] LUNCH detected: 12:00 PM")
                elif any(word in message_lower for word in ['afternoon']):
                    target_hour = 14
                    logger.info(f"☀️ [BULLETPROOF PARSER] AFTERNOON detected: 2:00 PM")
                elif any(word in message_lower for word in ['dinner']):
                    target_hour = 18
                    logger.info(f"🍽️ [BULLETPROOF PARSER] DINNER detected: 6:00 PM")
                elif any(word in message_lower for word in ['evening']):
                    target_hour = 19
                    logger.info(f"🌆 [BULLETPROOF PARSER] EVENING detected: 7:00 PM")
                elif any(word in message_lower for word in ['night']):
                    target_hour = 20
                    logger.info(f"🌃 [BULLETPROOF PARSER] NIGHT detected: 8:00 PM")
                else:
                    logger.info(f"⏰ [BULLETPROOF PARSER] NO TIME WORD - using default: 7:00 PM")
            
            # STEP 5: Combine date and time with the determined timezone
            try:
                result = datetime.combine(target_date, datetime.min.time().replace(hour=target_hour, minute=target_minute))
                result = result.replace(tzinfo=target_timezone)
                
                logger.info(f"✅ [BULLETPROOF PARSER] FINAL RESULT (timezone-aware): {result.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
                logger.info(f"🕰️ [BULLETPROOF PARSER] Using timezone: {target_timezone}")
                
                # STEP 6: Verification check
                if "tomorrow" in message_lower:
                    expected_date = (now + timedelta(days=1)).date()
                    if result.date() == expected_date:
                        logger.info(f"✅ [BULLETPROOF PARSER] VERIFICATION PASSED: Tomorrow correctly calculated")
                    else:
                        logger.error(f"❌ [BULLETPROOF PARSER] VERIFICATION FAILED!")
                        logger.error(f"   Expected: {expected_date} ({expected_date.strftime('%A')})")
                        logger.error(f"   Got: {result.date()} ({result.strftime('%A')})")
                
                return result
                
            except ValueError as e:
                logger.error(f"❌ [BULLETPROOF PARSER] Invalid time: hour={target_hour}, minute={target_minute}, error={e}")
                # Fallback to 7 PM with the determined timezone
                result = datetime.combine(target_date, datetime.min.time().replace(hour=19, minute=0))
                result = result.replace(tzinfo=target_timezone)
                logger.warning(f"⚠️ [BULLETPROOF PARSER] Using fallback time (timezone-aware): {result}")
                return result
                
        except Exception as e:
            logger.error(f"❌ [BULLETPROOF PARSER] Unexpected error: {e}")
            # Ultimate fallback: tomorrow at 7 PM with local timezone
            from datetime import timezone as dt_timezone
            import time
            
            now = datetime.now()
            local_offset = time.timezone if not time.daylight else time.altzone
            local_tz_offset = timedelta(seconds=-local_offset)
            local_tz = dt_timezone(local_tz_offset)
            
            fallback = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
            fallback = fallback.replace(tzinfo=local_tz)
            logger.warning(f"🆘 [BULLETPROOF PARSER] Ultimate fallback (timezone-aware): {fallback}")
            return fallback
    
    def _extract_meeting_title_from_message(self, message: str) -> str:
        """Extract meeting title/subject from SMS message using better patterns"""
        message_lower = message.lower().strip()
        
        # Pattern 1: "Schedule a meeting with X about Y"
        about_pattern = r'(?:schedule|meeting|call).*?(?:about|subject:|topic:)\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s+(?:tomorrow|today|this|next|at|with|\d)|\.?$)'
        match = re.search(about_pattern, message_lower, re.IGNORECASE)
        if match:
            title = match.group(1).strip().title()
            logger.info(f"📝 [TITLE EXTRACTION] Found title via 'about' pattern: '{title}'")
            return title
        
        # Pattern 2: "Schedule a meeting for Y"
        for_pattern = r'(?:schedule|meeting|call).*?for\s+([^\s]+(?:\s+[^\s]+)*?)(?:\s+(?:tomorrow|today|this|next|at|with|\d)|\.?$)'
        match = re.search(for_pattern, message_lower, re.IGNORECASE)
        if match:
            title = match.group(1).strip().title()
            logger.info(f"📝 [TITLE EXTRACTION] Found title via 'for' pattern: '{title}'")
            return title
        
        # Pattern 3: Look for quoted subjects
        quote_pattern = r'["\']([^"\']++)["\']'
        match = re.search(quote_pattern, message)
        if match:
            title = match.group(1).strip()
            logger.info(f"📝 [TITLE EXTRACTION] Found quoted title: '{title}'")
            return title
        
        # Pattern 4: Extract capitalized phrases that might be subjects
        words = message.split()
        capitalized_phrases = []
        current_phrase = []
        
        for word in words:
            # Skip common scheduling words
            if word.lower() in ['schedule', 'meeting', 'call', 'with', 'about', 'tomorrow', 'today', 'at', 'pm', 'am', 'and', 'the', 'a', 'an']:
                if current_phrase:
                    capitalized_phrases.append(' '.join(current_phrase))
                    current_phrase = []
                continue
            
            # Check if word looks like a subject word (capitalized or contains meaningful content)
            if word[0].isupper() or any(char.isalpha() for char in word):
                current_phrase.append(word)
            else:
                if current_phrase:
                    capitalized_phrases.append(' '.join(current_phrase))
                    current_phrase = []
        
        if current_phrase:
            capitalized_phrases.append(' '.join(current_phrase))
        
        # Find the most likely subject (longest meaningful phrase)
        for phrase in sorted(capitalized_phrases, key=len, reverse=True):
            if len(phrase) > 2 and not phrase.lower() in ['hari', 'sundar', 'rick']:  # Skip names only
                logger.info(f"📝 [TITLE EXTRACTION] Found capitalized phrase: '{phrase}'")
                return phrase
        
        # Fallback: try to find any meaningful words
        meaningful_words = []
        for word in words:
            if (len(word) > 2 and 
                word.lower() not in ['schedule', 'meeting', 'call', 'with', 'about', 'tomorrow', 'today', 'at', 'the', 'and', 'a', 'an'] and
                not re.match(r'^\d+', word) and  # Skip times
                not word.lower() in ['hari', 'sundar', 'thangavel', 'manickam']):
                meaningful_words.append(word)
        
        if meaningful_words:
            title = ' '.join(meaningful_words[:3])  # Take first 3 meaningful words
            logger.info(f"📝 [TITLE EXTRACTION] Using meaningful words: '{title}'")
            return title.title()
        
        # Final fallback
        logger.warning(f"📝 [TITLE EXTRACTION] No good title found, using fallback: 'Meeting'")
        return "Meeting"
    
    async def _get_team_context(self, team_member, db) -> Dict:
        """Get team context for LLM"""
        
        from database.models import Team, TeamMember
        
        team = db.query(Team).filter(Team.id == team_member.team_id).first()
        members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        
        return {
            "team_name": team.name if team else "Unknown",
            "members": [
                {
                    "name": member.name,
                    "phone": member.phone,
                    "is_admin": member.is_admin
                }
                for member in members
            ]
        }
    
    async def _basic_command_processing(self, message_text: str, team_member, conversation, db) -> str:
        """Simple fallback command processing when LLM not available"""
        try:
            message_lower = message_text.lower().strip()
            
            # Simple pattern matching for basic commands
            if any(word in message_lower for word in ['schedule', 'meeting', 'event']):
                if 'tomorrow' in message_lower:
                    return "I'd help you schedule that meeting for tomorrow! (LLM processing unavailable - using basic response)"
                elif any(day in message_lower for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                    return "I'd help you schedule that meeting! (LLM processing unavailable - using basic response)"
                else:
                    return "I can help you schedule a meeting. When would you like it? (LLM processing unavailable)"
            
            elif any(word in message_lower for word in ['list', 'show', 'meetings', 'agenda']):
                return "Here are your upcoming meetings: (No meetings found - LLM processing unavailable)"
            
            elif any(word in message_lower for word in ['cancel', 'delete', 'remove']):
                return "I can help you cancel a meeting. (LLM processing unavailable - please try again later)"
            
            elif any(word in message_lower for word in ['help', 'what', 'how']):
                return """🤖 I can help you with:
• "Schedule meeting tomorrow at 2pm"
• "List my meetings"  
• "Cancel today's meeting"

(LLM processing currently unavailable - using basic responses)"""
            else:
                return "I'm here to help with meeting coordination! Try asking me to schedule a meeting or list your meetings. (LLM processing unavailable)"
        except Exception as e:
            logger.error(f"❌ Basic command processing error: {e}")
            return "Sorry, I'm having trouble processing your request. Please try again later."

    async def _fallback_response(self, message: str, user) -> str:
        """
        Simple fallback when Claude is not available or overloaded
        """
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["schedule", "meeting", "plan"]):
            return f"Hi {user.name}! I'd help you schedule that, but my AI assistant is temporarily overloaded. Please try again in a few minutes."
        elif any(word in message_lower for word in ["list", "meetings", "calendar"]):
            return "I'd show you your calendar, but my AI assistant is temporarily overloaded. Try again in a few minutes."
        else:
            return f"Hi {user.name}! I'm your meeting coordinator. I can help schedule meetings, check your calendar, and more. (AI temporarily overloaded - please try again soon)"