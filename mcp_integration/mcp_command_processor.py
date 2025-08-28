# mcp_command_processor.py - Aggressive MCP tool usage for real actions
# This version forces the LLM to use tools instead of just talking

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import os
import re
from sqlalchemy.orm import Session

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    # logger not yet defined here, will log later

logger = logging.getLogger(__name__)

class MCPCommandProcessor:
    def __init__(self, sms_client, calendar_client, meet_client, strava_client=None):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        self.strava_client = strava_client
        # Detect calendar client signature (provider vs raw client)
        self._calendar_accepts_keywords = False
        try:
            import inspect
            sig = inspect.signature(getattr(self.calendar_client, 'create_event', lambda: None))
            params = list(sig.parameters.keys())
            # MCPCalendarProvider: (title, start, duration_minutes=60, attendees=None)
            if params[:2] == ['title','start']:
                self._calendar_mode = 'provider'
            else:
                self._calendar_mode = 'raw'
            # Check if keywords exist
            self._calendar_accepts_keywords = any(p == 'start_time' for p in params) or any(p == 'duration_minutes' for p in params)
        except Exception:
            self._calendar_mode = 'unknown'
        
        # Initialize Claude client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        logger.info(f"🔍 [MCP INIT] ANTHROPIC_AVAILABLE: {ANTHROPIC_AVAILABLE}")
        logger.info(f"🔍 [MCP INIT] ANTHROPIC_API_KEY present: {bool(api_key)}")
        logger.info(f"🔍 [MCP INIT] API_KEY starts with: {api_key[:10] if api_key else 'None'}...")
        
        if ANTHROPIC_AVAILABLE and api_key:
            try:
                self.claude_client = anthropic.Anthropic(
                    api_key=api_key
                )
                self.llm_enabled = True
                logger.info("✅ MCP Command Processor with Claude API enabled")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Anthropic client: {e}")
                self.claude_client = None
                self.llm_enabled = False
        else:
            self.claude_client = None
            self.llm_enabled = False
            if not ANTHROPIC_AVAILABLE:
                logger.warning("⚠️  Anthropic not available - MCP tools will be limited")
            elif not api_key:
                logger.warning("⚠️  ANTHROPIC_API_KEY not set - MCP tools will be limited")
                logger.warning("⚠️  ANTHROPIC_API_KEY not set - MCP tools will be limited")
            logger.info("📝 MCP Command Processor without LLM - using basic processing")
    
    async def process_command_with_llm(self, message_text: str, team_member, conversation, db: Session) -> str:
        """LLM-ONLY MODE: Process SMS command with Claude LLM and MCP tools - NO FALLBACKS"""

        if not self.llm_enabled or self.claude_client is None:
            return "❌ Claude LLM service is not available. Please ensure ANTHROPIC_API_KEY is properly configured in Railway environment variables."

        try:
            # Get team context
            team_context = await self._get_team_context(team_member, db)
            
            # Create AGGRESSIVE system prompt that forces tool usage
            system_prompt = self._create_action_focused_prompt(team_member, team_context)
            user_prompt = self._create_action_user_prompt(message_text, team_member)
            
            logger.info(f"🚀 AGGRESSIVE MCP processing: {message_text[:50]}...")
            
            # Call Claude with FORCED tool usage
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.0,  # No creativity - just actions
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=self._get_action_tools()
            )
            
            logger.info(f"🤖 Claude response blocks: {len(response.content)}")
            
            # Process response - REQUIRE tool usage for certain keywords
            return await self._process_action_response(response, team_member, db, message_text)
            
        except Exception as e:
            logger.error(f"LLM processing error: {e}", exc_info=True)
            return f"❌ LLM processing failed: {str(e)}. Please ensure ANTHROPIC_API_KEY is properly configured."
    
    def _create_action_focused_prompt(self, team_member, team_context: Dict) -> str:
        """Create system prompt that FORCES action instead of conversation"""
        return f"""You are an ACTION-ORIENTED family meeting coordinator. You DO NOT engage in conversation - you TAKE ACTIONS.

CONTEXT:
- User: {team_member.name}
- Team: {team_context['team_name']} ({len(team_context['members'])} members)
- Members: {', '.join([m['name'] for m in team_context['members']])}
- Current time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

CRITICAL RULES:
1. **NEVER respond conversationally** - "I can meet Sunday" is FORBIDDEN
2. **ALWAYS use tools for scheduling requests** - Use create_calendar_event for ANY meeting request
3. **TAKE IMMEDIATE ACTION** - Don't ask questions, just create events
4. **BE DECISIVE** - If time not specified, pick a reasonable time and create the event

TOOL USAGE REQUIREMENTS:
- ANY mention of "meeting", "schedule", "call", "dinner", "lunch", "breakfast" → MUST use create_calendar_event
- Questions about "when", "what time", "availability" → MUST use list_upcoming_events
- "Cancel" or "delete" or "remove" → MUST use appropriate tool
- "Move", "change", "reschedule", "update time" → MUST use update_calendar_event
- NEVER respond with just text for actionable requests

RESPONSE FORMAT:
- Use tools first, THEN provide confirmation
- Be brief: "✅ [Action taken] - [Event details]"
- Include meeting links and times
- NO conversational responses allowed

EXAMPLES OF FORBIDDEN RESPONSES:
❌ "I can meet this Sunday at 3pm"
❌ "Let me know if that works for you"
❌ "Would you like me to schedule that?"

REQUIRED RESPONSES:
✅ Use create_calendar_event → "✅ Meeting scheduled for Sunday 3pm - [meet link]"
✅ Use list_upcoming_events → "📅 Your meetings: [list]"
✅ Use update_calendar_event → "✅ Meeting moved to tomorrow 2pm"

Remember: YOU ARE AN ACTION SYSTEM, NOT A CONVERSATION PARTNER."""

    def _create_action_user_prompt(self, message_text: str, team_member) -> str:
        """Create user prompt that demands action"""
        return f"""INCOMING SMS REQUEST: "{message_text}"
FROM: {team_member.name}

ANALYZE THIS REQUEST AND TAKE IMMEDIATE ACTION:

1. Is this a scheduling request? → Use create_calendar_event immediately
2. Is this asking about meetings? → Use list_upcoming_events immediately  
3. Is this asking for availability? → Use find_calendar_free_time immediately
4. Is this a move/reschedule/update request? → Use update_calendar_event immediately

DO NOT RESPOND CONVERSATIONALLY. TAKE ACTION WITH TOOLS.

If this is about scheduling ANY kind of meeting/call/dinner/gathering:
- Parse the request for time/date hints
- Choose a reasonable time if not specified
- Create the actual calendar event using create_calendar_event
- Respond with confirmation and meeting details

If this is about moving/changing/rescheduling an existing meeting:
- Identify which meeting to update (may need to list events first)
- Parse the new time/date
- Use update_calendar_event with the event ID and new details
- Respond with confirmation of the change

ACTION REQUIRED NOW."""

    def _get_action_tools(self) -> List[Dict]:
        """Get tools optimized for action-taking"""
        return [
            {
                "name": "create_calendar_event",
                "description": "IMMEDIATELY create a real calendar event - USE THIS FOR ANY MEETING REQUEST",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title"},
                        "start_time": {"type": "string", "description": "Start time in ISO format or relative (tomorrow 7pm)"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes", "default": 60},
                        "description": {"type": "string", "description": "Event description"}
                    },
                    "required": ["title", "start_time"]
                }
            },
            {
                "name": "list_upcoming_events",
                "description": "Get upcoming calendar events - USE FOR 'what meetings' questions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer", "description": "Days to look ahead", "default": 7},
                        "limit": {"type": "integer", "description": "Max events", "default": 5}
                    }
                }
            },
            {
                "name": "update_calendar_event",
                "description": "UPDATE an existing calendar event - USE THIS FOR 'move meeting', 'change time', 'reschedule' requests",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "ID of the event to update"},
                        "title": {"type": "string", "description": "New event title (optional)"},
                        "start_time": {"type": "string", "description": "New start time in ISO format (optional)"},
                        "duration_minutes": {"type": "integer", "description": "New duration in minutes (optional)"},
                        "description": {"type": "string", "description": "New event description (optional)"}
                    },
                    "required": ["event_id"]
                }
            }
        ]
    
    async def _process_action_response(self, response, team_member, db, original_message: str) -> str:
        """Process Claude response with ACTION ENFORCEMENT"""
        
        tool_calls_made = []
        text_response = ""
        
        # Process all content blocks
        for content_block in response.content:
            if content_block.type == "tool_use":
                # GOOD - Claude is using tools
                tool_name = content_block.name
                tool_input = content_block.input
                
                logger.info(f"🎯 ACTION TAKEN: {tool_name} with {json.dumps(tool_input)}")
                
                # Execute the tool
                tool_result = await self._execute_action_tool(tool_name, tool_input, team_member, db)
                tool_calls_made.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": tool_result
                })
                
            elif content_block.type == "text":
                text_response = content_block.text
        
        # ENFORCEMENT: If this looks like a scheduling request but no tools were used, FORCE tool usage
        if self._is_scheduling_request(original_message) and not tool_calls_made:
            logger.warning(f"⚠️ FORCING TOOL USAGE - Claude tried to respond conversationally to: {original_message}")
            
            # Force create calendar event
            forced_result = await self._force_calendar_creation(original_message, team_member, db)
            if forced_result:
                return forced_result
        
        # ENFORCEMENT: If this looks like an update request but no tools were used, FORCE tool usage
        if self._is_update_request(original_message) and not tool_calls_made:
            logger.warning(f"⚠️ FORCING UPDATE TOOL USAGE - Claude tried to respond conversationally to: {original_message}")
            
            # Force update calendar event
            forced_result = await self._force_calendar_update(original_message, team_member, db)
            if forced_result:
                return forced_result
        
        # Generate final response based on tool results
        if tool_calls_made:
            return await self._generate_action_confirmation(tool_calls_made, team_member)
        else:
            # Fallback for non-actionable messages
            return text_response or "I'm ready to help! Try: 'Schedule family meeting tomorrow at 7pm'"
    
    def _is_scheduling_request(self, message: str) -> bool:
        """Detect if message is requesting to schedule something"""
        scheduling_keywords = [
            "schedule", "meeting", "call", "dinner", "lunch", "breakfast",
            "get together", "plan", "organize", "set up", "arrange",
            "family time", "catch up", "discussion"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in scheduling_keywords)
    
    def _is_update_request(self, message: str) -> bool:
        """Detect if message is requesting to update/move/reschedule something"""
        update_keywords = [
            "move", "change", "reschedule", "update", "shift", "postpone",
            "delay", "bring forward", "push back", "adjust", "modify",
            "rearrange", "relocate", "switch", "transfer"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in update_keywords)
    
    async def _force_calendar_creation(self, message: str, team_member, db) -> Optional[str]:
        """Force create a calendar event when Claude didn't use tools"""
        
        try:
            logger.info(f"🔨 FORCING calendar event creation for: {message}")
            
            # Parse message for hints
            title = self._extract_meeting_title(message)
            start_time = self._extract_meeting_time(message)
            
            if not start_time:
                return "I couldn't understand the meeting time. Please specify a time like 'tomorrow at 2pm'"
            
            # Create the event directly
            tool_result = await self._execute_action_tool("create_calendar_event", {
                "title": title,
                "start_time": start_time.isoformat(),
                "duration_minutes": 60
            }, team_member, db)
            
            if tool_result.get("success"):
                event_data = tool_result
                return f"""✅ Meeting scheduled!

📅 {event_data.get('title')}
🕐 {event_data.get('start_time')}
🔗 {event_data.get('meet_link', 'Meeting link will be provided')}

✨ Created automatically via SMS"""
            
        except Exception as e:
            logger.error(f"❌ Force creation failed: {e}")
        
        return None
    
    async def _force_calendar_update(self, message: str, team_member, db) -> Optional[str]:
        """Force update a calendar event when Claude didn't use tools"""
        
        try:
            logger.info(f"🔨 FORCING calendar event update for: {message}")
            
            # First, list upcoming events to find the most recent meeting
            list_result = await self._execute_action_tool("list_upcoming_events", {
                "days_ahead": 7,
                "limit": 10
            }, team_member, db)
            
            if not list_result.get("success") or not list_result.get("events"):
                return "I couldn't find any upcoming meetings to update. Please create a meeting first."
            
            # Get the most recent upcoming meeting
            events = list_result.get("events", [])
            if not events:
                return "No upcoming meetings found to update."
            
            # Sort by start time and get the next upcoming meeting
            upcoming_events = []
            for event in events:
                start_time_str = event.get("start_time_iso")  # Use ISO format instead of formatted string
                if start_time_str:
                    try:
                        # Parse ISO format with timezone
                        if start_time_str.endswith('Z'):
                            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        else:
                            start_time = datetime.fromisoformat(start_time_str)
                        
                        # Convert to UTC for comparison
                        if start_time.tzinfo is None:
                            start_time = start_time.replace(tzinfo=timezone.utc)
                        else:
                            start_time = start_time.astimezone(timezone.utc)
                            
                        now_utc = datetime.now(timezone.utc)
                        if start_time > now_utc:
                            upcoming_events.append(event)
                    except Exception as parse_error:
                        logger.warning(f"⚠️ Failed to parse event time '{start_time_str}': {parse_error}")
                        continue
            
            if not upcoming_events:
                return "No upcoming meetings found to update."
            
            # Sort by start time
            upcoming_events.sort(key=lambda x: x.get("start_time", ""))
            target_event = upcoming_events[0]
            event_id = target_event.get("id")
            
            if not event_id:
                return "I couldn't identify the meeting to update."
            
            # Parse message for new time
            new_start_time = self._extract_meeting_time(message)
            
            if not new_start_time:
                return "I couldn't understand the new meeting time. Please specify a time like 'tomorrow at 2pm'"
            
            # Update the event
            update_result = await self._execute_action_tool("update_calendar_event", {
                "event_id": event_id,
                "start_time": new_start_time.isoformat(),
                "duration_minutes": 60
            }, team_member, db)
            
            if update_result.get("success"):
                event_data = update_result
                return f"""✅ Meeting updated!

📅 {event_data.get('title')}
🕐 {event_data.get('start_time')} (updated)
🔗 {event_data.get('meet_link', 'Meeting link unchanged')}

✨ Updated automatically via SMS"""
            
        except Exception as e:
            logger.error(f"❌ Force update failed: {e}")
        
        return None
    
    def _extract_meeting_title(self, message: str) -> str:
        """Extract meeting title/subject from SMS message using better patterns"""
        import re
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

    def _extract_mentioned_names(self, message: str) -> List[str]:
        """Extract names mentioned in the message for selective invitations"""
        import re
        
        # Common name patterns
        name_patterns = [
            r'\bwith\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',  # "with John" or "with John Smith"
            r'\bfor\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',   # "for Mary" 
            r'\band\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',   # "and David"
            r'\bplus\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',  # "plus Sarah"
            r'\b([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+and\s+me',  # "John and me"
            r'\b([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+only',   # "John only"
        ]
        
        mentioned_names = []
        message_lower = message.lower()
        
        for pattern in name_patterns:
            matches = re.findall(pattern, message_lower)
            for match in matches:
                # Clean up the name (remove extra spaces, capitalize)
                name = ' '.join(word.capitalize() for word in match.split())
                if len(name) > 1 and name not in mentioned_names:  # Avoid single letters
                    mentioned_names.append(name)
        
        logger.info(f"👥 [MCP] Extracted names from message: {mentioned_names}")
        return mentioned_names
        """Extract meeting title from message"""
        message_lower = message.lower()
        
        # Look for common patterns
        if "about" in message_lower:
            # "meeting about vacation" -> "Vacation Meeting"
            parts = message_lower.split("about")
            if len(parts) > 1:
                topic = parts[1].strip().split()[0:3]  # First few words
                return " ".join(word.title() for word in topic) + " Meeting"
        
        if "dinner" in message_lower:
            return "Family Dinner"
        elif "lunch" in message_lower:
            return "Family Lunch"
        elif "call" in message_lower:
            return "Family Call"
        elif "meeting" in message_lower:
            return "Family Meeting"
        
        return "Family Get-Together"
    
    def _extract_meeting_time(self, message: str) -> Optional[datetime]:
        """Extract meeting time from message with proper parsing"""
        
        logger.info(f"🕰️ [MCP DATETIME DEBUG] Original input: '{message}'")
        logger.info(f"🕰️ [MCP] Parsing datetime string: '{message}'")
        
        try:
            # Parse natural language date/time
            # Use UTC consistently and convert to Eastern Time at the end
            now_utc = datetime.now(timezone.utc)
            now = now_utc - timedelta(hours=4)  # Convert to Eastern Time (UTC-4, ignoring DST for simplicity)
            
            time_lower = message.lower().strip()
            
            logger.info(f"� [MCP] Processing natural language: '{time_lower}'")
            logger.info(f"�️ [MCP] Current Eastern Time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
            
            # Extract date part
            base_date = None
            if "tomorrow" in time_lower:
                logger.info(f"📅 [MCP] TOMORROW CALCULATION:")
                logger.info(f"   Today is {now.strftime('%A %B %d, %Y')}")
                
                tomorrow = now + timedelta(days=1)
                logger.info(f"   Tomorrow will be {tomorrow.strftime('%A %B %d, %Y')}")
                
                base_date = tomorrow.date()
                logger.info(f"   Using date: {base_date}")
            elif "today" in time_lower:
                base_date = now.date()
                logger.info(f"📅 [MCP] Date: today = {base_date}")
            elif "weekend" in time_lower or "saturday" in time_lower:
                # Next Saturday
                days_until_saturday = (5 - now.weekday()) % 7
                if days_until_saturday == 0:
                    days_until_saturday = 7
                base_date = (now + timedelta(days=days_until_saturday)).date()
                logger.info(f"📅 [MCP] Date: next saturday = {base_date}")
            elif "sunday" in time_lower:
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0:
                    days_until_sunday = 7
                base_date = (now + timedelta(days=days_until_sunday)).date()
                logger.info(f"📅 [MCP] Date: next sunday = {base_date}")
            else:
                # Try to find day names (monday, tuesday, etc.)
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for i, day in enumerate(days):
                    if day in time_lower:
                        days_ahead = (i - now.weekday()) % 7
                        if days_ahead == 0:
                            days_ahead = 7  # Next week if it's the same day
                        base_date = (now + timedelta(days=days_ahead)).date()
                        logger.info(f"📅 [MCP] Date: next {day} = {base_date}")
                        break
                
                if not base_date:
                    # Default to tomorrow if no date found
                    base_date = (now + timedelta(days=1)).date()
                    logger.warning(f"⚠️ [MCP] No date found, defaulting to tomorrow: {base_date}")
            
            # Extract time part
            hour = 19  # Default to 7 PM
            minute = 0
            
            # Look for time patterns
            import re
            
            # Pattern 1: "2pm", "2 pm", "14:00", "2:30pm", "2:30 pm"
            time_patterns = [
                r'(\d{1,2})\s*:?\s*(\d{2})?\s*(pm|am)',  # 2pm, 2:30pm, 2 pm, 2:30 pm
                r'(\d{1,2})\s*:?\s*(\d{2})',            # 14:00, 2:30
                r'(\d{1,2})\s*(pm|am)',                  # 2pm, 2am
            ]
            
            time_found = False
            for pattern in time_patterns:
                match = re.search(pattern, time_lower)
                if match:
                    hour_str = match.group(1)
                    minute_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else "0"
                    am_pm = match.group(3) if len(match.groups()) > 2 else None
                    
                    hour = int(hour_str)
                    minute = int(minute_str) if minute_str and minute_str.isdigit() else 0
                    
                    # Handle AM/PM
                    if am_pm:
                        if am_pm == 'pm' and hour != 12:
                            hour += 12
                        elif am_pm == 'am' and hour == 12:
                            hour = 0
                    elif hour < 8:  # If no AM/PM specified and hour < 8, assume PM
                        hour += 12
                    
                    time_found = True
                    logger.info(f"🕰️ [MCP] Time extracted: {hour:02d}:{minute:02d} from '{match.group(0)}'")
                    break
            
            if not time_found:
                # Look for common time words
                if "morning" in time_lower:
                    hour = 9
                    logger.info("🌅 [MCP] Time: morning = 9:00 AM")
                elif "afternoon" in time_lower:
                    hour = 14
                    logger.info("☀️ [MCP] Time: afternoon = 2:00 PM")
                elif "evening" in time_lower:
                    hour = 18
                    logger.info("🌆 [MCP] Time: evening = 6:00 PM")
                elif "night" in time_lower:
                    hour = 20
                    logger.info("🌃 [MCP] Time: night = 8:00 PM")
                elif "dinner" in time_lower:
                    hour = 18
                    logger.info("🍽️ [MCP] Time: dinner = 6:00 PM")
                elif "lunch" in time_lower:
                    hour = 12
                    logger.info("🍽️ [MCP] Time: lunch = 12:00 PM")
                else:
                    logger.warning(f"⚠️ [MCP] No time found in '{message}', defaulting to 7:00 PM")
            
            # Combine date and time with timezone awareness
            logger.info(f"📅 [MCP FINAL DEBUG] About to combine date and time:")
            logger.info(f"   base_date: {base_date}")
            logger.info(f"   hour: {hour}, minute: {minute}")
            
            from datetime import timezone as dt_timezone
            import time
            
            result = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
            
            # Add timezone info - use Eastern Time (UTC-4) instead of system timezone
            # This ensures times are interpreted correctly by Google Calendar
            eastern_tz = timezone(timedelta(hours=-4))  # Eastern Time (simplified, ignoring DST)
            result = result.replace(tzinfo=eastern_tz)
            
            logger.info(f"📅 [MCP FINAL DEBUG] Combined result (Eastern Time): {result}")
            logger.info(f"📅 [MCP FINAL DEBUG] Result weekday: {result.weekday()} (0=Mon, 1=Tue, 2=Wed)")
            logger.info(f"✅ [MCP] Final parsed datetime: {result.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
            
            # Double-check the math using the same timezone approach
            if "tomorrow" in message.lower():
                expected_date = (now + timedelta(days=1)).date()
                if result.date() != expected_date:
                    logger.error(f"🐛 [MCP] BUG DETECTED!")
                    logger.error(f"   Expected tomorrow: {expected_date} ({expected_date.strftime('%A')})")
                    logger.error(f"   Actually got: {result.date()} ({result.strftime('%A')})")
                    logger.error(f"   Difference: {(result.date() - expected_date).days} days")
                else:
                    logger.info(f"✅ [MCP] Date calculation verified correct for 'tomorrow' (Eastern Time)")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [MCP] Failed to parse datetime: {message}, error: {e}")
            # Return tomorrow at 7 PM as fallback with Eastern Time
            eastern_tz = timezone(timedelta(hours=-4))  # Eastern Time (simplified, ignoring DST)
                        
            fallback = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
            # Add Eastern Time timezone info
            fallback = fallback.replace(tzinfo=eastern_tz)
            logger.warning(f"⚠️ [MCP] Using fallback datetime (Eastern Time): {fallback}")
            return fallback
    
    async def _execute_action_tool(self, tool_name: str, tool_input: Dict, team_member, db) -> Dict:
        """Execute tools with real MCP calendar integration"""
        
        try:
            if tool_name == "create_calendar_event":
                return await self._create_real_calendar_event(tool_input, team_member, db)
            elif tool_name == "list_upcoming_events":
                return await self._list_real_events(tool_input, team_member, db)
            elif tool_name == "find_calendar_free_time":
                return await self._find_real_free_time(tool_input, team_member, db)
            elif tool_name == "update_calendar_event":
                return await self._update_real_calendar_event(tool_input, team_member, db)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return {"error": str(e)}
    
    async def _create_real_calendar_event(self, input_data: Dict, team_member, db) -> Dict:
        """Create real calendar event using MCP client"""
        
        try:
            # Parse time
            start_time_str = input_data["start_time"]
            if isinstance(start_time_str, str):
                if start_time_str.startswith("20"):  # ISO format
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    # Relative time parsing
                    start_time = self._extract_meeting_time(start_time_str)
            else:
                start_time = self._extract_meeting_time("tomorrow evening")
            
            if not start_time:
                return {"success": False, "error": "Could not parse meeting time"}
            
            logger.info(f"🗓️ [MCP] CALENDAR EVENT CREATION ATTEMPT:")
            logger.info(f"   Title: {input_data['title']}")
            logger.info(f"   Start time: {start_time}")
            logger.info(f"   Duration: {input_data.get('duration_minutes', 60)} minutes")
            
            # Get team members for attendees
            from database.models import Team, TeamMember
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
            
            logger.info(f"👥 [MCP] Team members found: {len(team_members)}")
            for member in team_members:
                logger.info(f"   - {member.name} ({member.phone}) - Email: {member.email or 'MISSING'}")
            
            # Extract attendee emails - ONLY if specifically mentioned in the message
            attendee_emails = []
            
            # Parse message for specific names
            mentioned_names = self._extract_mentioned_names(input_data.get("description", "") + " " + input_data["title"])
            logger.info(f"👥 [MCP] Names mentioned in message: {mentioned_names}")
            
            if mentioned_names:
                # Only invite specifically mentioned people
                for member in team_members:
                    if member.email and member.name and any(name.lower() in member.name.lower() for name in mentioned_names):
                        attendee_emails.append(member.email)
                        logger.info(f"✅ [MCP] Adding attendee: {member.name} ({member.email})")
            
            logger.info(f"👥 [MCP] Final attendee emails: {attendee_emails}")
            
            if not attendee_emails:
                logger.info("ℹ️ [MCP] No specific attendees mentioned - creating meeting without invites")
            else:
                logger.info(f"✅ [MCP] Will send invites to {len(attendee_emails)} attendees: {', '.join(attendee_emails)}")
            
            # Create Google Meet link (defensive: meet_client may be None in some boot paths)
            logger.info(f"🔗 [MCP] Creating Google Meet link...")
            meet_link = None
            try:
                if self.meet_client and hasattr(self.meet_client, 'create_meeting'):
                    meet_link = await self.meet_client.create_meeting(input_data["title"])
                else:
                    raise AttributeError("meet_client missing; generating fallback link")
            except Exception as e:
                import uuid
                fallback_id = uuid.uuid4().hex[:8]
                meet_link = f"https://meet.google.com/{fallback_id}-auto"
                logger.warning(f"⚠️ [MCP] Meet client unavailable ({e}); using fallback link {meet_link}")
            logger.info(f"✅ [MCP] Meet link ready: {meet_link}")
            
            # Use the calendar client (support heterogeneous signatures by using positional args)
            logger.info(f"📅 [MCP] Creating calendar event via calendar client (mode={getattr(self,'_calendar_mode','?')})...")
            duration = input_data.get("duration_minutes", 60)
            event = None
            try:
                if getattr(self,'_calendar_mode','') == 'provider':
                    # MCPCalendarProvider signature: (title, start, duration_minutes=60, attendees=None)
                    event = await self.calendar_client.create_event(
                        input_data["title"],
                        start_time,
                        duration,
                        attendee_emails
                    )
                else:
                    # Assume raw RealMCPCalendarClient style with kwargs
                    event = await self.calendar_client.create_event(
                        title=input_data["title"],
                        start_time=start_time,
                        duration_minutes=duration,
                        attendees=attendee_emails,
                        meet_link=meet_link
                    )
            except TypeError as te:
                logger.warning(f"⚠️ [MCP] First create_event attempt failed ({te}); trying alternate signature")
                try:
                    if getattr(self,'_calendar_mode','') == 'provider':
                        event = await self.calendar_client.create_event(
                            input_data["title"], start_time, duration, attendee_emails
                        )
                    else:
                        event = await self.calendar_client.create_event(
                            input_data["title"], start_time, duration, attendee_emails, meet_link
                        )
                except Exception as e2:
                    logger.error(f"❌ [MCP] Calendar create_event failed after retries: {e2}")
                    return {"success": False, "error": f"Calendar client unsupported signature: {e2}"}
            
            logger.info(f"📊 [MCP] Calendar client response: {event}")
            
            if event:
                logger.info(f"✅ [MCP] Calendar event created successfully")
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
                
                logger.info(f"💾 [MCP] Meeting saved to database with ID: {meeting.id}")
                
                return {
                    "success": True,
                    "title": input_data["title"],
                    "start_time": start_time.strftime("%A, %B %d at %I:%M %p"),
                    "meet_link": meet_link,
                    "event_id": event.get("id"),
                    "calendar_source": event.get("source", "unknown"),
                    "attendees_count": len(attendee_emails),
                    "real_calendar_event": event.get("source") != "mock"
                }
            else:
                logger.error(f"❌ [MCP] Calendar client returned None/False")
                return {"success": False, "error": "Calendar client failed to create event"}
            
        except Exception as e:
            logger.error(f"❌ [MCP] Real calendar event creation failed: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _list_real_events(self, input_data: Dict, team_member, db) -> Dict:
        """List real events"""
        try:
            events = await self.calendar_client.list_events(
                days_ahead=input_data.get("days_ahead", 7),
                limit=input_data.get("limit", 5)
            )
            
            return {
                "success": True,
                "events": events,
                "count": len(events)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _find_real_free_time(self, input_data: Dict, team_member, db) -> Dict:
        """Find real free time"""
        try:
            free_time = await self.calendar_client.find_free_time(
                attendees=[],  # Add team member emails
                duration_minutes=input_data.get("duration_minutes", 60)
            )
            
            if free_time:
                return {
                    "success": True,
                    "suggested_time": free_time.strftime("%A, %B %d at %I:%M %p")
                }
            
            return {"success": False, "message": "No free time found"}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _update_real_calendar_event(self, input_data: Dict, team_member, db) -> Dict:
        """Update real calendar event using MCP client"""
        
        try:
            event_id = input_data["event_id"]
            logger.info(f"� [MCP] Updating calendar event: {event_id}")
            
            # Prepare update data
            update_data = {}
            
            if "title" in input_data:
                update_data["title"] = input_data["title"]
                logger.info(f"   Title: {input_data['title']}")
                
            if "start_time" in input_data:
                start_time_str = input_data["start_time"]
                if isinstance(start_time_str, str):
                    if start_time_str.startswith("20"):  # ISO format
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    else:
                        # Natural language time parsing (e.g., "tomorrow 3pm")
                        start_time = self._extract_meeting_time(start_time_str)
                else:
                    start_time = self._extract_meeting_time("tomorrow evening")
                
                if start_time:
                    update_data["start_time"] = start_time
                    logger.info(f"   Start time: {start_time}")
            
            if "duration_minutes" in input_data:
                update_data["duration_minutes"] = input_data["duration_minutes"]
                logger.info(f"   Duration: {input_data['duration_minutes']} minutes")
                
            if "description" in input_data:
                update_data["description"] = input_data["description"]
                logger.info(f"   Description: {input_data['description']}")
            
            # Use the calendar client to update the event
            logger.info(f"📅 [MCP] Updating calendar event via calendar client...")
            updated_event = await self.calendar_client.update_event(
                event_id=event_id,
                **update_data
            )
            
            logger.info(f"📊 [MCP] Calendar client update response: {updated_event}")
            
            if updated_event:
                logger.info(f"✅ [MCP] Calendar event updated successfully")
                logger.info(f"   Event ID: {updated_event.get('id')}")
                logger.info(f"   Source: {updated_event.get('source', 'unknown')}")
                
                # Update database record if it exists
                from database.models import Meeting
                meeting = db.query(Meeting).filter(Meeting.google_calendar_event_id == event_id).first()
                if meeting:
                    if "title" in update_data:
                        meeting.title = update_data["title"]
                    if "start_time" in update_data:
                        meeting.scheduled_time = update_data["start_time"]
                    if "description" in update_data:
                        meeting.description = update_data["description"]
                    db.commit()
                    logger.info(f"💾 [MCP] Meeting updated in database")
                
                start_time_obj = update_data.get("start_time")
                return {
                    "success": True,
                    "title": updated_event.get("title", update_data.get("title", "Updated Meeting")),
                    "start_time": start_time_obj.strftime("%A, %B %d at %I:%M %p") if isinstance(start_time_obj, datetime) else "Time unchanged",
                    "event_id": updated_event.get("id"),
                    "calendar_source": updated_event.get("source", "unknown"),
                    "real_calendar_event": updated_event.get("source") != "mock"
                }
            else:
                logger.error(f"❌ [MCP] Calendar client returned None/False for update")
                return {"success": False, "error": "Calendar client failed to update event"}
            
        except Exception as e:
            logger.error(f"❌ [MCP] Real calendar event update failed: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _generate_action_confirmation(self, tool_results: List[Dict], team_member) -> str:
        """Generate confirmation message based on actions taken"""
        
        for result in tool_results:
            tool_name = result["tool"]
            tool_result = result["result"]
            
            if tool_name == "create_calendar_event" and tool_result.get("success"):
                return f"""✅ Meeting scheduled!

📅 {tool_result.get('title')}
🕐 {tool_result.get('start_time')}
🔗 {tool_result.get('meet_link')}

{f"✨ Using {tool_result.get('calendar_source')} calendar" if tool_result.get('calendar_source') else ''}"""
            
            elif tool_name == "update_calendar_event" and tool_result.get("success"):
                return f"""✅ Meeting updated!

📅 {tool_result.get('title')}
🕐 {tool_result.get('start_time')}

{f"✨ Using {tool_result.get('calendar_source')} calendar" if tool_result.get('calendar_source') else ''}"""
            
            elif tool_name == "list_upcoming_events" and tool_result.get("success"):
                events = tool_result.get("events", [])
                if events:
                    response = "📅 Your upcoming meetings:\\n\\n"
                    for i, event in enumerate(events[:3], 1):
                        response += f"{i}. {event.get('title')}\\n   {event.get('start_time')}\\n\\n"
                    return response.strip()
                else:
                    return "📅 No upcoming meetings scheduled."
        
        return "✅ Action completed!"
    
    async def _get_team_context(self, team_member, db) -> Dict:
        """Get team context"""
        from database.models import Team, TeamMember
        
        team = db.query(Team).filter(Team.id == team_member.team_id).first()
        members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        
        return {
            "team_name": team.name if team else "Unknown",
            "members": [
                {"name": member.name, "phone": member.phone}
                for member in members
            ]
        }
    
    async def _basic_command_processing(self, message_text: str, team_member, conversation, db) -> str:
        """LLM-ONLY MODE: Return error message since LLM is required"""
        return "❌ LLM service is required for this feature. Please ensure ANTHROPIC_API_KEY is properly configured."

    def _is_list_request(self, message_text: str) -> bool:
        """Check if message is requesting to list meetings"""
        return any(word in message_text.lower() for word in ['list', 'show', 'what', 'upcoming', 'meetings'])

    def _is_cancel_request(self, message_text: str) -> bool:
        """Check if message is requesting to cancel a meeting"""
        return any(word in message_text.lower() for word in ['cancel', 'delete', 'remove'])