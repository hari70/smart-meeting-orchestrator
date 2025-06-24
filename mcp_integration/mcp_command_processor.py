# mcp_command_processor.py - Aggressive MCP tool usage for real actions
# This version forces the LLM to use tools instead of just talking

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

class MCPCommandProcessor:
    def __init__(self, sms_client, calendar_client, meet_client, strava_client=None):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        self.strava_client = strava_client
        
        # Initialize Claude client
        if ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            self.claude_client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            self.llm_enabled = True
            logger.info("✅ MCP Command Processor with Claude API enabled")
        else:
            self.claude_client = None
            self.llm_enabled = False
            logger.info("📝 MCP Command Processor without LLM - using basic processing")
    
    async def process_command_with_llm(self, message_text: str, team_member, conversation, db: Session) -> str:
        """Process SMS command with FORCED tool usage - no conversational responses allowed"""
        
        if not self.llm_enabled:
            return await self._basic_command_processing(message_text, team_member, conversation, db)
        
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
            logger.error(f"❌ MCP processing error: {e}")
            return await self._basic_command_processing(message_text, team_member, conversation, db)
    
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
- ANY mention of "meeting", "schedule", "call", "dinner", "get together" → MUST use create_calendar_event
- Questions about "when", "what time", "availability" → MUST use list_upcoming_events
- "Cancel" or "delete" → MUST use appropriate tool
- NEVER respond with just text for actionable requests

RESPONSE FORMAT:
- Use tools first, THEN provide confirmation
- Be brief: "✅ [Action taken] - [Event details]"
- Include meeting links and times
- NO conversational responses allowed

EXAMPLES OF FORBIDDEN RESPONSES:
❌ "Hi! I can meet this Sunday at 3pm"
❌ "Let me know if that works for you"
❌ "Would you like me to schedule that?"

REQUIRED RESPONSES:
✅ Use create_calendar_event → "✅ Meeting scheduled for Sunday 3pm - [meet link]"
✅ Use list_upcoming_events → "📅 Your meetings: [list]"

Remember: YOU ARE AN ACTION SYSTEM, NOT A CONVERSATION PARTNER."""

    def _create_action_user_prompt(self, message_text: str, team_member) -> str:
        """Create user prompt that demands action"""
        return f"""INCOMING SMS REQUEST: "{message_text}"
FROM: {team_member.name}

ANALYZE THIS REQUEST AND TAKE IMMEDIATE ACTION:

1. Is this a scheduling request? → Use create_calendar_event immediately
2. Is this asking about meetings? → Use list_upcoming_events immediately  
3. Is this asking for availability? → Use find_calendar_free_time immediately

DO NOT RESPOND CONVERSATIONALLY. TAKE ACTION WITH TOOLS.

If this is about scheduling ANY kind of meeting/call/dinner/gathering:
- Parse the request for time/date hints
- Choose a reasonable time if not specified
- Create the actual calendar event using create_calendar_event
- Respond with confirmation and meeting details

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
                "name": "find_calendar_free_time", 
                "description": "Find available time slots - USE FOR availability questions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {"type": "integer", "description": "Required duration", "default": 60},
                        "date_preference": {"type": "string", "description": "Preferred timeframe"}
                    }
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
    
    async def _force_calendar_creation(self, message: str, team_member, db) -> Optional[str]:
        """Force create a calendar event when Claude didn't use tools"""
        
        try:
            logger.info(f"🔨 FORCING calendar event creation for: {message}")
            
            # Parse message for hints
            title = self._extract_meeting_title(message)
            start_time = self._extract_meeting_time(message)
            
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
    
    def _extract_meeting_title(self, message: str) -> str:
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
    
    def _extract_meeting_time(self, message: str) -> datetime:
        """Extract meeting time from message with proper parsing"""
        
        logger.info(f"🕰️ [MCP] Parsing datetime string: '{message}'")
        
        try:
            # Parse natural language date/time
            now = datetime.now()
            time_lower = message.lower().strip()
            
            logger.info(f"🔍 [MCP] Processing natural language: '{time_lower}'")
            
            # Extract date part
            base_date = None
            if "tomorrow" in time_lower:
                tomorrow = now + timedelta(days=1)
                base_date = tomorrow.date()
                logger.info(f"📅 [MCP] TOMORROW CALCULATION:")
                logger.info(f"   Today is {now.strftime('%A %B %d, %Y')}")
                logger.info(f"   Tomorrow will be {tomorrow.strftime('%A %B %d, %Y')}")
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
            
            # Combine date and time
            result = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
            logger.info(f"✅ [MCP] Final parsed datetime: {result.strftime('%A, %B %d, %Y at %I:%M %p')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [MCP] Failed to parse datetime: {message}, error: {e}")
            # Return tomorrow at 7 PM as fallback
            fallback = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
            logger.warning(f"⚠️ [MCP] Using fallback datetime: {fallback}")
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
            
            # Extract attendee emails (skip the event creator to avoid duplicate)
            attendee_emails = [member.email for member in team_members if member.email and member.phone != team_member.phone]
            logger.info(f"👥 [MCP] Attendee emails extracted: {attendee_emails}")
            
            if not attendee_emails:
                logger.warning("⚠️ [MCP] No attendee emails found! Event will be created without invites.")
                logger.warning("💡 [MCP] Make sure family members have email addresses in the database.")
            else:
                logger.info(f"✅ [MCP] Will send invites to {len(attendee_emails)} attendees: {', '.join(attendee_emails)}")
            
            # Create Google Meet link
            logger.info(f"🔗 [MCP] Creating Google Meet link...")
            meet_link = await self.meet_client.create_meeting(input_data["title"])
            logger.info(f"✅ [MCP] Meet link created: {meet_link}")
            
            # Use the calendar client (which should be RealMCPCalendarClient if enabled)
            logger.info(f"📅 [MCP] Creating calendar event via calendar client...")
            event = await self.calendar_client.create_event(
                title=input_data["title"],
                start_time=start_time,
                duration_minutes=input_data.get("duration_minutes", 60),
                attendees=attendee_emails,  # Now using real attendee emails!
                meet_link=meet_link
            )
            
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
        """Fallback processing"""
        if self._is_scheduling_request(message_text):
            return await self._force_calendar_creation(message_text, team_member, db) or "I can help you schedule that! Please provide more details."
        
        return "I'm ready to help with scheduling! Try: 'Schedule family meeting tomorrow at 7pm'"