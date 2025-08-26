"""
Intelligent Meeting Coordinator - Clean Architecture
===================================================

This is the AI-first approach where:
1. SMS is just a communication channel
2. LLM understands natural language completely
3. LLM calls MCP tools to take actions
4. No manual parsing - LLM handles everything

Architecture: SMS → LLM → MCP Tools → Response
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
from sqlalchemy.orm import Session

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)

class IntelligentCoordinator:
    """
    AI-First Meeting Coordinator
    
    Principles:
    - SMS is just input/output - no parsing
    - LLM understands everything
    - MCP tools do the actual work
    - Simple, clean, reliable
    """
    
    def __init__(self, calendar_client, meet_client, sms_client):
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        self.sms_client = sms_client
        
        # Initialize Claude
        if ANTHROPIC_AVAILABLE and anthropic and os.getenv("ANTHROPIC_API_KEY"):
            self.claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.enabled = True
            logger.info("🤖 Intelligent Coordinator initialized with Claude")
        else:
            self.claude = None
            self.enabled = False
            logger.warning("❌ Intelligent Coordinator disabled - no Anthropic API key")
    
    async def process_message(self, message: str, user, conversation, db: Session) -> str:
        """
        Process any message through AI intelligence
        
        This is the ONLY entry point - no manual logic, no parsing
        """
        if not self.enabled:
            return await self._fallback_response(message, user)
        
        try:
            # Build context for LLM
            context = await self._build_context(user, conversation, db)
            
            # Let Claude understand and act
            response = await self._claude_process(message, context, user, db)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Intelligent processing failed: {e}")
            return await self._fallback_response(message, user)
    
    async def _claude_process(self, message: str, context: Dict, user, db: Session) -> str:
        """
        Let Claude understand the message and use tools
        
        No manual logic - Claude decides everything
        """
        
        # Create the system prompt
        system_prompt = self._create_system_prompt(user, context)
        
        # User message with context
        user_prompt = f"""
Current message from {user.name}: "{message}"

{self._format_context(context)}

Analyze this message and take appropriate action using your tools.
Remember: You are their meeting coordinator. If they want to schedule something, 
use the tools to actually do it. Don't just respond conversationally.
"""
        
        # Call Claude with tools
        if not self.claude:
            return "AI assistant temporarily unavailable"
            
        try:
            response = self.claude.messages.create(  # type: ignore
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=self._get_mcp_tools()
            )
        except Exception as e:
            logger.error(f"❌ Claude API call failed: {e}")
            return f"Sorry, I had trouble processing that: {str(e)}"
        
        # Process Claude's response
        return await self._process_claude_response(response, user, db)
    
    def _create_system_prompt(self, user, context: Dict) -> str:
        """
        Create a clean, focused system prompt
        
        Key: Tell Claude to USE TOOLS, not just talk
        """
        current_time = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')
        user_timezone = context.get('timezone', 'US/Eastern')
        
        return f"""You are an intelligent meeting coordinator for {user.name}.

CURRENT CONTEXT:
- Date/Time: {current_time} ({user_timezone})
- User: {user.name}
- Team: {context.get('team_name', 'Family')}

YOUR ROLE:
You coordinate meetings through SMS. When users ask you to do something, you USE TOOLS to actually do it.

CRITICAL RULES:
1. For scheduling requests → USE create_calendar_event tool
2. For calendar questions → USE list_calendar_events tool  
3. For availability → USE check_calendar_conflicts tool
4. For timezone confusion → ASK for clarification but PRESERVE context

TIMEZONE HANDLING:
If time zone is ambiguous (like "4pm"), ask: "Do you mean 4pm Eastern Time?"
But REMEMBER what they're trying to schedule and complete it once clarified.

RESPONSE STYLE:
- Direct and helpful
- Use tools to take action
- Ask for clarification when truly needed
- Keep responses under 160 characters when possible (SMS)

TOOL USAGE:
You MUST use tools for any actionable request. Don't just respond conversationally.
If someone says "schedule a meeting", actually create the calendar event."""

    def _get_mcp_tools(self) -> List[Dict]:
        """
        Define clean MCP tools for Claude
        
        Simplified, focused tools that actually work
        """
        return [
            {
                "name": "create_calendar_event",
                "description": "Create a real calendar event with Google Meet link",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string", 
                            "description": "Meeting title/subject"
                        },
                        "when": {
                            "type": "string",
                            "description": "When to schedule (e.g., 'tomorrow at 4pm', 'Friday at 2pm ET')"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes",
                            "default": 60
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Who to invite (names or emails)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional meeting description"
                        }
                    },
                    "required": ["title", "when"]
                }
            },
            {
                "name": "list_calendar_events",
                "description": "List upcoming calendar events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {
                            "type": "integer",
                            "description": "How many days to look ahead",
                            "default": 7
                        },
                        "today_only": {
                            "type": "boolean",
                            "description": "Only show today's events",
                            "default": False
                        }
                    }
                }
            },
            {
                "name": "check_calendar_conflicts",
                "description": "Check if a time slot is available",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "when": {
                            "type": "string",
                            "description": "Time to check (e.g., 'tomorrow at 4pm ET')"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration to check",
                            "default": 60
                        }
                    },
                    "required": ["when"]
                }
            },
            {
                "name": "ask_for_clarification",
                "description": "Ask user for clarification while preserving context",
                "input_schema": {
                    "type": "object", 
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "What to ask the user"
                        },
                        "context_to_preserve": {
                            "type": "object",
                            "description": "Context to remember for when they answer"
                        }
                    },
                    "required": ["question"]
                }
            }
        ]
    
    async def _process_claude_response(self, response, user, db: Session) -> str:
        """
        Process Claude's response and execute any tool calls
        
        This is where the actual work happens
        """
        result_text = ""
        
        # Process each part of Claude's response
        for content in response.content:
            if content.type == "text":
                result_text = content.text
                
            elif content.type == "tool_use":
                # Execute the tool
                tool_result = await self._execute_tool(
                    content.name, 
                    content.input, 
                    user, 
                    db
                )
                
                # If tool was successful, use its result
                if tool_result.get("success"):
                    result_text = tool_result.get("message", result_text)
                else:
                    result_text = f"Sorry, I had trouble {content.name.replace('_', ' ')}: {tool_result.get('error', 'Unknown error')}"
        
        return result_text or "I'm here to help coordinate your meetings!"
    
    async def _execute_tool(self, tool_name: str, tool_input: Dict, user, db: Session) -> Dict:
        """
        Execute MCP tools cleanly
        
        Each tool does ONE thing well
        """
        try:
            if tool_name == "create_calendar_event":
                return await self._tool_create_event(tool_input, user, db)
                
            elif tool_name == "list_calendar_events":
                return await self._tool_list_events(tool_input, user, db)
                
            elif tool_name == "check_calendar_conflicts":
                return await self._tool_check_conflicts(tool_input, user, db)
                
            elif tool_name == "ask_for_clarification":
                return await self._tool_ask_clarification(tool_input, user, db)
                
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _tool_create_event(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Create calendar event - the core functionality
        
        Simple: Parse time, create event, return confirmation
        """
        try:
            title = input_data["title"]
            when = input_data["when"]
            duration = input_data.get("duration_minutes", 60)
            attendees = input_data.get("attendees", [])
            description = input_data.get("description", "")
            
            # Smart time parsing (but simple)
            start_time = await self._parse_when(when)
            if not start_time:
                return {
                    "success": False, 
                    "error": f"Couldn't understand when '{when}' means. Try 'tomorrow at 4pm ET'"
                }
            
            # Create Google Meet link
            meet_link = await self.meet_client.create_meeting(title)
            
            # Get attendee emails
            attendee_emails = await self._resolve_attendees(attendees, user, db)
            
            # Create calendar event
            event = await self.calendar_client.create_event(
                title=title,
                start_time=start_time,
                duration_minutes=duration,
                attendees=attendee_emails,
                meet_link=meet_link
            )
            
            if event:
                # Save to database
                await self._save_meeting(event, user, db, meet_link, start_time, title)
                
                # Format response
                attendee_count = len(attendee_emails)
                attendee_text = f" with {attendee_count} people" if attendee_count > 0 else ""
                
                return {
                    "success": True,
                    "message": f"✅ {title} scheduled for {start_time.strftime('%A at %I:%M %p ET')}{attendee_text}! Meet link: {meet_link}"
                }
            else:
                return {"success": False, "error": "Failed to create calendar event"}
                
        except Exception as e:
            logger.error(f"❌ Create event failed: {e}")
            return {"success": False, "error": f"Failed to create event: {str(e)}"}
    
    async def _tool_list_events(self, input_data: Dict, user, db: Session) -> Dict:
        """
        List calendar events cleanly
        """
        try:
            days_ahead = input_data.get("days_ahead", 7)
            today_only = input_data.get("today_only", False)
            
            if today_only:
                days_ahead = 1
            
            # Get events from calendar
            events = await self.calendar_client.list_events(days_ahead=days_ahead, limit=10)
            
            if not events:
                period = "today" if today_only else f"next {days_ahead} days"
                return {
                    "success": True,
                    "message": f"📅 No meetings scheduled for {period}"
                }
            
            # Format events nicely
            event_list = []
            for event in events[:5]:  # Limit to 5 for SMS
                title = event.get("title", "Meeting")
                time = event.get("start_time", "Time TBD")
                event_list.append(f"• {title} - {time}")
            
            period = "today" if today_only else f"next {days_ahead} days"
            events_text = "\n".join(event_list)
            
            return {
                "success": True,
                "message": f"📅 Your meetings for {period}:\n{events_text}"
            }
            
        except Exception as e:
            logger.error(f"❌ List events failed: {e}")
            return {"success": False, "error": "Failed to get calendar events"}
    
    async def _tool_check_conflicts(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Check calendar conflicts
        """
        try:
            when = input_data["when"]
            duration = input_data.get("duration_minutes", 60)
            
            # Parse the time
            start_time = await self._parse_when(when)
            if not start_time:
                return {"success": False, "error": f"Couldn't understand '{when}'"}
            
            # Check for conflicts
            conflicts = await self.calendar_client.check_conflicts(
                start_time=start_time,
                duration_minutes=duration
            )
            
            if conflicts.get("has_conflicts"):
                conflict_list = conflicts.get("conflicts", [])
                conflict_names = [c.get("title", "Meeting") for c in conflict_list]
                
                return {
                    "success": True,
                    "message": f"❌ Conflict at {start_time.strftime('%A at %I:%M %p ET')} with: {', '.join(conflict_names)}"
                }
            else:
                return {
                    "success": True,
                    "message": f"✅ {start_time.strftime('%A at %I:%M %p ET')} is available"
                }
                
        except Exception as e:
            logger.error(f"❌ Check conflicts failed: {e}")
            return {"success": False, "error": "Failed to check calendar conflicts"}
    
    async def _tool_ask_clarification(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Ask for clarification while preserving context
        """
        try:
            question = input_data["question"]
            context_to_preserve = input_data.get("context_to_preserve", {})
            
            # Store the context for when they respond
            await self._store_pending_context(user, context_to_preserve, db)
            
            return {
                "success": True,
                "message": question
            }
            
        except Exception as e:
            logger.error(f"❌ Ask clarification failed: {e}")
            return {"success": False, "error": "Failed to ask for clarification"}
    
    # ===============================
    # HELPER METHODS (Keep Simple)
    # ===============================
    
    async def _parse_when(self, when_text: str) -> Optional[datetime]:
        """
        Simple, reliable time parsing
        
        If we can't parse it, return None and let Claude ask for clarification
        """
        try:
            from dateutil import parser
            from datetime import datetime, timedelta
            import re
            
            when_lower = when_text.lower()
            now = datetime.now()
            
            # Handle relative dates
            if "tomorrow" in when_lower:
                base_date = (now + timedelta(days=1)).date()
            elif "today" in when_lower:
                base_date = now.date()
            else:
                # Try to parse as absolute date
                try:
                    parsed = parser.parse(when_text, fuzzy=True)
                    return parsed
                except:
                    return None
            
            # Extract time
            time_match = re.search(r'(\d{1,2}):?(\d{0,2})\s*(am|pm|a\.m\.|p\.m\.)', when_lower)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                ampm = time_match.group(3)
                
                if 'p' in ampm and hour != 12:
                    hour += 12
                elif 'a' in ampm and hour == 12:
                    hour = 0
                
                result = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                
                # Add timezone (default to ET)
                import pytz
                et_tz = pytz.timezone('US/Eastern')
                result = et_tz.localize(result)
                
                return result
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Time parsing failed for '{when_text}': {e}")
            return None
    
    async def _resolve_attendees(self, attendees: List[str], user, db: Session) -> List[str]:
        """
        Convert attendee names to email addresses
        """
        try:
            from database.models import TeamMember
            
            emails = []
            team_members = db.query(TeamMember).filter(TeamMember.team_id == user.team_id).all()
            
            for attendee in attendees:
                # If it's already an email, use it
                if '@' in attendee:
                    emails.append(attendee)
                    continue
                
                # Look for team member by name
                for member in team_members:
                    if (attendee.lower() in member.name.lower() or 
                        member.name.lower() in attendee.lower()):
                        if member.email is not None and member.phone != user.phone:
                            emails.append(member.email)
                            break
            
            return emails
            
        except Exception as e:
            logger.warning(f"⚠️ Attendee resolution failed: {e}")
            return []
    
    async def _save_meeting(self, event: Dict, user, db: Session, meet_link: str, start_time: datetime, title: str):
        """
        Save meeting to database
        """
        try:
            from database.models import Meeting
            
            meeting = Meeting(
                team_id=user.team_id,
                title=title,
                scheduled_time=start_time,
                google_meet_link=meet_link,
                google_calendar_event_id=event.get("id"),
                created_by_phone=user.phone,
                description=f"Created via SMS"
            )
            
            db.add(meeting)
            db.commit()
            
        except Exception as e:
            logger.warning(f"⚠️ Database save failed: {e}")
    
    async def _build_context(self, user, conversation, db: Session) -> Dict:
        """
        Build context for Claude (keep it simple)
        """
        try:
            from database.models import Team
            
            team = db.query(Team).filter(Team.id == user.team_id).first()
            
            context = {
                "team_name": team.name if team else "Family",
                "timezone": "US/Eastern",  # Default, but Claude can ask for clarification
                "conversation_history": []
            }
            
            # Add recent conversation if available
            if conversation and conversation.context:
                recent = conversation.context.get("recent_messages", [])
                if recent:
                    context["conversation_history"] = recent[-3:]  # Last 3 messages
            
            return context
            
        except Exception as e:
            logger.warning(f"⚠️ Context building failed: {e}")
            return {"team_name": "Family", "timezone": "US/Eastern"}
    
    def _format_context(self, context: Dict) -> str:
        """
        Format context for Claude
        """
        parts = []
        
        if context.get("conversation_history"):
            parts.append("Recent conversation:")
            for msg in context["conversation_history"]:
                timestamp = msg.get("timestamp", "")
                message = msg.get("message", "")
                if message:
                    parts.append(f"  - {message}")
        
        return "\n".join(parts) if parts else ""
    
    async def _store_pending_context(self, user, context: Dict, db: Session):
        """
        Store context for follow-up questions
        """
        try:
            from database.models import Conversation
            
            conversation = db.query(Conversation).filter(
                Conversation.phone_number == user.phone
            ).first()
            
            if conversation:
                # Get current context or initialize empty dict
                current_context = conversation.context or {}  # type: ignore
                
                # Add pending clarification
                current_context["pending_clarification"] = {  # type: ignore
                    "context": context,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Update the conversation context
                conversation.context = current_context  # type: ignore
                
                db.commit()
                
        except Exception as e:
            logger.warning(f"⚠️ Context storage failed: {e}")
    
    async def _fallback_response(self, message: str, user) -> str:
        """
        Simple fallback when Claude is not available
        """
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["schedule", "meeting", "plan"]):
            return f"Hi {user.name}! I'd help you schedule that, but my AI assistant is temporarily unavailable. Please try again in a moment."
        elif any(word in message_lower for word in ["list", "meetings", "calendar"]):
            return "I'd show you your calendar, but my AI assistant is temporarily unavailable. Try again in a moment."
        else:
            return f"Hi {user.name}! I'm your meeting coordinator. I can help schedule meetings, check your calendar, and more. (AI temporarily unavailable)"