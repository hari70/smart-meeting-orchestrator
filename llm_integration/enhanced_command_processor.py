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

class LLMCommandProcessor:
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
            logger.info("✅ LLM integration enabled with Claude API")
        else:
            self.claude_client = None
            self.llm_enabled = False
            logger.info("📝 LLM integration disabled - using basic processing")
        
        # Define available MCP tools
        self.available_tools = self._define_mcp_tools()
        
    def _define_mcp_tools(self) -> List[Dict]:
        """Define available MCP tools for Claude to use"""
        return [
            {
                "name": "create_calendar_event",
                "description": "Create a new calendar event with attendees and Google Meet link",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Event title"},
                        "start_time": {"type": "string", "description": "Start time in ISO format"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes", "default": 60},
                        "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee names"},
                        "description": {"type": "string", "description": "Event description"}
                    },
                    "required": ["title", "start_time"]
                }
            },
            {
                "name": "find_calendar_free_time",
                "description": "Find free time slots for scheduling meetings",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {"type": "integer", "description": "Required duration", "default": 60},
                        "preferred_times": {"type": "array", "items": {"type": "string"}, "description": "Preferred time hints"},
                        "date_range": {"type": "string", "description": "Date range like 'this week', 'next week'"}
                    },
                    "required": ["duration_minutes"]
                }
            },
            {
                "name": "list_upcoming_events",
                "description": "Get list of upcoming calendar events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
                        "limit": {"type": "integer", "description": "Maximum number of events", "default": 5}
                    }
                }
            },
            {
                "name": "get_strava_recent_activities",
                "description": "Get recent fitness activities to understand workout schedule",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of activities", "default": 5},
                        "activity_type": {"type": "string", "description": "Filter by type (run, bike, etc.)"}
                    }
                }
            }
        ]
    
    async def process_command_with_llm(self, message_text: str, team_member, conversation, db: Session) -> str:
        """Process SMS command using LLM with MCP tool access"""
        
        if not self.llm_enabled:
            # Fallback to basic processing
            return await self._basic_command_processing(message_text, team_member, conversation, db)
        
        try:
            # Get team context
            team_context = await self._get_team_context(team_member, db)
            
            # Create LLM prompt with tool access
            system_prompt = self._create_system_prompt(team_member, team_context)
            user_prompt = self._create_user_prompt(message_text, team_member)
            
            logger.info(f"🧠 Processing with LLM: {message_text[:50]}...")
            
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
            return await self._process_llm_response(response, team_member, db)
            
        except Exception as e:
            logger.error(f"❌ LLM processing error: {e}")
            return await self._basic_command_processing(message_text, team_member, conversation, db)
    
    def _create_system_prompt(self, team_member, team_context: Dict) -> str:
        """Create system prompt for Claude with MCP context"""
        return f"""You are a smart family meeting coordinator with access to Google Calendar and Strava fitness data.

CONTEXT:
- User: {team_member.name} (Phone: {team_member.phone})
- Team: {team_context['team_name']} ({len(team_context['members'])} members)
- Members: {', '.join([m['name'] for m in team_context['members']])}
- Current time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}

CAPABILITIES:
You can use these MCP tools to coordinate meetings intelligently:
1. create_calendar_event - Schedule meetings with Google Meet links
2. find_calendar_free_time - Find when everyone is available  
3. list_upcoming_events - Check existing calendar commitments
4. get_strava_recent_activities - Check recent workouts for optimal timing

INSTRUCTIONS:
1. Parse natural language requests intelligently
2. Use tools when you need real data (don't assume)
3. Be proactive - if someone wants to schedule, create the actual event
4. Consider fitness context - avoid meetings right after intense workouts
5. Always provide helpful, actionable responses
6. Format responses for SMS (concise but informative)

RESPONSE STYLE:
- Use emojis appropriately (📅 🕐 👥 🔗 💪)
- Keep messages under 300 characters when possible  
- Always confirm what action was taken
- Include relevant details (time, attendees, links)
- Be friendly and family-oriented

SMART COORDINATION:
- If asked to schedule, actually use create_calendar_event
- If asked about availability, use find_calendar_free_time
- If someone mentions workouts, check get_strava_recent_activities
- Always create Google Meet links for virtual meetings

Remember: You're helping families coordinate better by understanding both calendars AND fitness patterns!"""

    def _create_user_prompt(self, message_text: str, team_member) -> str:
        """Create user prompt with SMS context"""
        return f"""SMS from {team_member.name}: "{message_text}"

Please help coordinate this request using the available MCP tools. Consider:
1. What specific action is being requested?
2. Do I need to check calendars or fitness data first?
3. What information should I gather before responding?
4. How can I provide the most helpful response?

Use the MCP tools as needed and provide a helpful SMS response. If you're scheduling something, actually create the event!"""

    async def _process_llm_response(self, response, team_member, db) -> str:
        """Process Claude's response and execute any tool calls"""
        
        tool_results = []
        final_text = ""
        
        # Process all content blocks
        for content_block in response.content:
            if content_block.type == "tool_use":
                # Execute tool
                tool_name = content_block.name
                tool_input = content_block.input
                
                logger.info(f"🔧 Executing MCP tool: {tool_name} with input: {json.dumps(tool_input, indent=2)}")
                
                tool_result = await self._execute_mcp_tool(tool_name, tool_input, team_member, db)
                tool_results.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": tool_result
                })
                
            elif content_block.type == "text":
                final_text = content_block.text
        
        # If tools were used, get Claude's final response based on results
        if tool_results:
            logger.info(f"🎯 Tool execution complete. Getting final response from Claude...")
            
            tool_summary = "\\n".join([
                f"{result['tool']}: {result['result']}"
                for result in tool_results
            ])
            
            final_response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=400,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": f"Based on these tool results, provide a helpful SMS response to {team_member.name}:\\n\\nTool Results:\\n{tool_summary}\\n\\nKeep it concise, friendly, and include relevant details like meeting links or times."}
                ]
            )
            
            return final_response.content[0].text
        
        else:
            # Claude responded directly without tools
            return final_text if final_text else "I'm here to help! Try asking me to schedule a meeting or check your calendar."
    
    async def _execute_mcp_tool(self, tool_name: str, tool_input: Dict, team_member, db) -> Dict:
        """Execute specific MCP tool and return results"""
        
        try:
            if tool_name == "create_calendar_event":
                return await self._tool_create_calendar_event(tool_input, team_member, db)
            
            elif tool_name == "find_calendar_free_time":
                return await self._tool_find_free_time(tool_input, team_member, db)
            
            elif tool_name == "list_upcoming_events":
                return await self._tool_list_events(tool_input, team_member, db)
            
            elif tool_name == "get_strava_recent_activities":
                return await self._tool_get_strava_activities(tool_input, team_member)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def _tool_create_calendar_event(self, input_data: Dict, team_member, db) -> Dict:
        """Create calendar event using MCP calendar client"""
        
        try:
            # Parse start time - handle various formats
            start_time_str = input_data["start_time"]
            start_time = self._parse_datetime(start_time_str)
            
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
            
            # Use emails for attendees (skip the event creator to avoid duplicate)
            attendee_emails = [member.email for member in team_members if member.email and member.phone != team_member.phone]
            logger.info(f"👥 Attendee emails extracted: {attendee_emails}")
            
            # Debug: Show all team members and their email status
            for member in team_members:
                logger.info(f"👤 Team member: {member.name} ({member.phone}) - Email: {member.email or 'MISSING'}")
            
            if not attendee_emails:
                logger.warning("⚠️ No attendee emails found! Event will be created without invites.")
                logger.warning("💡 Make sure family members have email addresses in the database.")
            else:
                logger.info(f"✅ Will send invites to {len(attendee_emails)} attendees: {', '.join(attendee_emails)}")
            
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
    
    async def _tool_list_events(self, input_data: Dict, team_member, db) -> Dict:
        """List upcoming events"""
        
        try:
            from database.models import Meeting
            
            days_ahead = input_data.get("days_ahead", 7)
            limit = input_data.get("limit", 5)
            
            end_date = datetime.now() + timedelta(days=days_ahead)
            
            meetings = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > datetime.now(),
                Meeting.scheduled_time <= end_date
            ).order_by(Meeting.scheduled_time).limit(limit).all()
            
            if not meetings:
                return {"success": True, "events": [], "message": "No upcoming meetings"}
            
            events = []
            for meeting in meetings:
                events.append({
                    "title": meeting.title,
                    "time": meeting.scheduled_time.strftime("%A, %B %d at %I:%M %p"),
                    "meet_link": meeting.google_meet_link
                })
            
            return {
                "success": True,
                "events": events,
                "count": len(events)
            }
            
        except Exception as e:
            return {"error": f"Failed to list events: {str(e)}"}
    
    async def _tool_find_free_time(self, input_data: Dict, team_member, db) -> Dict:
        """Find free time using calendar client"""
        
        try:
            from database.models import Team, TeamMember
            
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
            
            duration = input_data.get("duration_minutes", 60)
            
            # Use calendar client to find free time
            free_time = await self.calendar_client.find_free_time(
                attendees=[member.google_calendar_id for member in members if member.google_calendar_id],
                duration_minutes=duration
            )
            
            if free_time:
                return {
                    "success": True,
                    "suggested_time": free_time.strftime("%A, %B %d at %I:%M %p"),
                    "duration_minutes": duration
                }
            else:
                return {
                    "success": False,
                    "message": "No suitable free time found"
                }
                
        except Exception as e:
            return {"error": f"Failed to find free time: {str(e)}"}
    
    async def _tool_get_strava_activities(self, input_data: Dict, team_member) -> Dict:
        """Get Strava activities for fitness context"""
        
        if not self.strava_client:
            # Mock Strava data for demonstration
            return {
                "success": True,
                "recent_workouts": [
                    {"type": "Run", "date": "2025-06-21", "duration": 45, "intensity": "moderate"},
                    {"type": "Bike", "date": "2025-06-20", "duration": 90, "intensity": "high"},
                    {"type": "Run", "date": "2025-06-19", "duration": 30, "intensity": "easy"}
                ],
                "analysis": {
                    "high_intensity_days": ["Wednesday", "Saturday"],
                    "recommendation": "Best meeting times: Thursday afternoon, Friday morning",
                    "note": "Mock Strava data - real integration available"
                }
            }
        
        try:
            # Real Strava integration would go here
            activities = await self.strava_client.get_athlete_activities(
                limit=input_data.get("limit", 5)
            )
            
            return {
                "success": True,
                "recent_workouts": activities,
                "analysis": self._analyze_workout_patterns(activities)
            }
            
        except Exception as e:
            return {"error": f"Failed to get Strava data: {e}"}
    
    def _parse_datetime(self, time_str: str) -> Optional[datetime]:
        """Parse various datetime formats"""
        
        logger.info(f"🕰️ Parsing datetime string: '{time_str}'")
        
        try:
            # Try ISO format first
            if 'T' in time_str or '+' in time_str:
                result = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                logger.info(f"✅ Parsed ISO format: {result}")
                return result
            
            # Use consistent timezone (America/New_York) instead of server time
            try:
                import pytz
                eastern = pytz.timezone('America/New_York')
                now = datetime.now(eastern)
                logger.info(f"🌍 Using timezone: America/New_York")
                logger.info(f"🕰️ Current time in timezone: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
            except ImportError:
                # Fallback to server time if pytz not available
                now = datetime.now()
                eastern = None
                logger.warning("⚠️ pytz not available, using server timezone")
            
            time_lower = time_str.lower().strip()
            
            logger.info(f"🔍 Processing natural language: '{time_lower}'")
            
            # Extract date part
            base_date = None
            if "tomorrow" in time_lower:
                base_date = (now + timedelta(days=1)).date()
                logger.info(f"📅 Date: tomorrow = {base_date} ({(now + timedelta(days=1)).strftime('%A')})")
            elif "today" in time_lower:
                base_date = now.date()
                logger.info(f"📅 Date: today = {base_date} ({now.strftime('%A')})")
            elif "weekend" in time_lower or "saturday" in time_lower:
                # Next Saturday
                days_until_saturday = (5 - now.weekday()) % 7
                if days_until_saturday == 0:
                    days_until_saturday = 7
                base_date = (now + timedelta(days=days_until_saturday)).date()
                logger.info(f"📅 Date: next saturday = {base_date}")
            elif "sunday" in time_lower:
                days_until_sunday = (6 - now.weekday()) % 7
                if days_until_sunday == 0:
                    days_until_sunday = 7
                base_date = (now + timedelta(days=days_until_sunday)).date()
                logger.info(f"📅 Date: next sunday = {base_date}")
            else:
                # Try to find day names (monday, tuesday, etc.)
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for i, day in enumerate(days):
                    if day in time_lower:
                        days_ahead = (i - now.weekday()) % 7
                        if days_ahead == 0:
                            days_ahead = 7  # Next week if it's the same day
                        base_date = (now + timedelta(days=days_ahead)).date()
                        logger.info(f"📅 Date: next {day} = {base_date}")
                        break
                
                if not base_date:
                    # Default to tomorrow if no date found
                    base_date = (now + timedelta(days=1)).date()
                    logger.warning(f"⚠️ No date found, defaulting to tomorrow: {base_date}")
            
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
                    logger.info(f"🕰️ Time extracted: {hour:02d}:{minute:02d} from '{match.group(0)}'")
                    break
            
            if not time_found:
                # Look for common time words
                if "morning" in time_lower:
                    hour = 9
                    logger.info("🌅 Time: morning = 9:00 AM")
                elif "afternoon" in time_lower:
                    hour = 14
                    logger.info("☀️ Time: afternoon = 2:00 PM")
                elif "evening" in time_lower:
                    hour = 18
                    logger.info("🌆 Time: evening = 6:00 PM")
                elif "night" in time_lower:
                    hour = 20
                    logger.info("🌃 Time: night = 8:00 PM")
                else:
                    logger.warning(f"⚠️ No time found in '{time_str}', defaulting to 7:00 PM")
            
            # Combine date and time
            if eastern:
                # Create as naive datetime first, then localize to Eastern
                naive_dt = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                result = eastern.localize(naive_dt)
                logger.info(f"✅ Final parsed datetime: {result.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
                # Return as naive datetime for compatibility with existing code
                return result.replace(tzinfo=None)
            else:
                # Fallback without timezone
                result = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                logger.info(f"✅ Final parsed datetime: {result.strftime('%A, %B %d, %Y at %I:%M %p')}")
                return result
            
        except Exception as e:
            logger.error(f"❌ Failed to parse datetime: {time_str}, error: {e}")
            # Return tomorrow at 7 PM as fallback
            try:
                import pytz
                eastern = pytz.timezone('America/New_York')
                now = datetime.now(eastern)
                fallback_naive = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
                fallback = eastern.localize(fallback_naive).replace(tzinfo=None)
                logger.warning(f"⚠️ Using fallback datetime: {fallback}")
                return fallback
            except:
                # Ultimate fallback
                fallback = datetime.combine((datetime.now() + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
                logger.warning(f"⚠️ Using ultimate fallback datetime: {fallback}")
                return fallback
    
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
        """Fallback to basic processing when LLM not available"""
        
        from sms_coordinator.command_processor import CommandProcessor
        
        # Use your existing command processor as fallback
        basic_processor = CommandProcessor(self.sms_client, self.calendar_client, self.meet_client)
        
        return await basic_processor.process_command(
            message_text=message_text,
            team_member=team_member,
            conversation=conversation,
            db=db
        )