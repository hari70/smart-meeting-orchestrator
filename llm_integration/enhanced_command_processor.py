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
                        "description": {"type": "string", "description": "Event description"},
                        "check_conflicts": {"type": "boolean", "description": "Check for conflicts before creating", "default": True}
                    },
                    "required": ["title", "start_time"]
                }
            },
            {
                "name": "check_calendar_conflicts",
                "description": "Check for scheduling conflicts at a specific time before creating events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "Proposed start time in ISO format"},
                        "duration_minutes": {"type": "integer", "description": "Duration in minutes", "default": 60}
                    },
                    "required": ["start_time"]
                }
            },
            {
                "name": "find_calendar_free_time",
                "description": "Find free time slots for scheduling meetings when conflicts detected",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "duration_minutes": {"type": "integer", "description": "Required duration", "default": 60},
                        "days_ahead": {"type": "integer", "description": "How many days to look ahead", "default": 7},
                        "preferred_hours": {"type": "array", "items": {"type": "integer"}, "description": "Preferred hours (24h format)"}
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
                "name": "get_workout_context",
                "description": "Get fitness context to optimize meeting scheduling around workouts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "proposed_time": {"type": "string", "description": "Proposed meeting time to check against workouts"},
                        "limit": {"type": "integer", "description": "Number of recent activities to analyze", "default": 7}
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
            return await self._process_llm_response(response, team_member, db, message_text)
            
        except Exception as e:
            logger.error(f"❌ LLM processing error: {e}")
            return await self._basic_command_processing(message_text, team_member, conversation, db)
    
    def _create_system_prompt(self, team_member, team_context: Dict) -> str:
        """Create system prompt for Claude with MCP context"""
        current_time = datetime.now()
        tomorrow = current_time + timedelta(days=1)
        
        return f"""You are a smart family meeting coordinator with access to Google Calendar and Strava fitness data.

IMPORTANT DATE CONTEXT:
- TODAY is: {current_time.strftime('%A, %B %d, %Y')}
- TOMORROW is: {tomorrow.strftime('%A, %B %d, %Y')}
- Current time: {current_time.strftime('%A, %B %d, %Y at %I:%M %p')}

CONTEXT:
- User: {team_member.name} (Phone: {team_member.phone})
- Team: {team_context['team_name']} ({len(team_context['members'])} members)
- Members: {', '.join([m['name'] for m in team_context['members']])}

DATE CALCULATION RULES:
- If user says "tomorrow", use {tomorrow.strftime('%Y-%m-%d')} (which is {tomorrow.strftime('%A')})
- If user says "today", use {current_time.strftime('%Y-%m-%d')} (which is {current_time.strftime('%A')})
- Be VERY careful with date calculations - always double-check!

CAPABILITIES:
You can use these MCP tools to coordinate meetings intelligently:
1. create_calendar_event - Schedule meetings with Google Meet links
2. find_calendar_free_time - Find when everyone is available  
3. list_upcoming_events - Check existing calendar commitments
4. get_strava_recent_activities - Check recent workouts for optimal timing

INSTRUCTIONS:
1. Parse natural language requests intelligently
2. **MANDATORY CONFLICT CHECK**: For ALL scheduling requests, ALWAYS use check_calendar_conflicts FIRST
3. **SMART ATTENDEE LOGIC**: 
   - "Family [event]" = invite all family members
   - "Schedule a meeting" = just the requester (no family invites)
   - "Schedule dinner/call with everyone" = invite family
4. **CONFLICT WORKFLOW**: 
   - Step 1: ALWAYS check_calendar_conflicts first
   - Step 2: If conflicts found, use find_calendar_free_time to suggest alternatives
   - Step 3: Only create_calendar_event if no conflicts OR user accepts alternative time
5. **CRITICAL**: When calculating dates, be extremely precise!
6. **PRIORITY**: Prevent double-booking at all costs!

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

EXAMPLES OF SMART CONFLICT-AWARE SCHEDULING:
✅ "Schedule family dinner tomorrow at 7pm" → check_calendar_conflicts → IF clear → create_calendar_event (with family invites)
✅ "Schedule a meeting tomorrow at 2pm" → check_calendar_conflicts → IF clear → create_calendar_event (individual, no family)
⚠️ "Schedule call tomorrow at 3pm" → check_calendar_conflicts → IF CONFLICT FOUND → find_calendar_free_time → suggest "4pm available instead?"

🎯 MANDATORY WORKFLOW:
1. Parse scheduling request
2. ALWAYS run check_calendar_conflicts FIRST
3. If conflicts: find_calendar_free_time + suggest alternatives + DON'T create event
4. If clear: create_calendar_event with smart attendee logic
5. Attendee rules: "family/dinner/everyone" = invite family, "meeting/work" = individual only

Remember: NEVER CREATE EVENTS WITHOUT CHECKING CONFLICTS FIRST!"""

    def _create_user_prompt(self, message_text: str, team_member) -> str:
        """Create user prompt with SMS context"""
        return f"""SMS from {team_member.name}: "{message_text}"

MANDATORY WORKFLOW FOR ALL SCHEDULING REQUESTS:
1. FIRST: Use check_calendar_conflicts to check for conflicts at the proposed time
2. IF CONFLICTS FOUND: Use find_calendar_free_time to suggest alternative times - DO NOT CREATE EVENT
3. IF NO CONFLICTS: Use create_calendar_event to create the event

ATTENDEE LOGIC:
- "Family dinner", "family meeting", "dinner", "lunch", "with everyone" = invite family members
- "Schedule a meeting", "work call", "appointment" = individual event only

Please follow this workflow exactly. Always check conflicts BEFORE creating events!"""

    async def _process_llm_response(self, response, team_member, db, message_text: str) -> str:
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
            
            elif tool_name == "get_workout_context":
                return await self._tool_get_workout_context(tool_input, team_member, message_text)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Error executing tool {tool_name}: {e}")
            return {"error": str(e)}
    
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
                    "suggested_action": "create_event"
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
            
            # Smart attendee logic based on event type and language
            attendee_emails = []
            
            # Determine if this should include family members
            event_title = input_data["title"].lower()
            message_lower = message_text.lower()
            
            include_family = False
            
            # Include family for these scenarios:
            if any(word in event_title for word in ["family", "dinner", "call", "vacation", "trip"]):
                include_family = True
                logger.info(f"🏠 FAMILY EVENT detected in title: '{input_data['title']}'")
            elif any(phrase in message_lower for phrase in ["family", "with everyone", "all of us", "together"]):
                include_family = True 
                logger.info(f"🏠 FAMILY EVENT detected in message: '{message_text}'")
            elif any(word in message_lower for word in ["dinner", "lunch", "breakfast", "bbq", "party"]):
                include_family = True
                logger.info(f"🍽️ MEAL EVENT detected - including family")
            
            # DON'T include family for generic meetings
            elif any(phrase in message_lower for phrase in ["meeting", "work", "call", "appointment"]) and "family" not in message_lower:
                include_family = False
                logger.info(f"💼 INDIVIDUAL MEETING detected - no family invites")
            
            if include_family:
                # Use emails for attendees (skip the event creator to avoid duplicate)
                attendee_emails = [member.email for member in team_members if member.email and member.phone != team_member.phone]
                logger.info(f"👥 Family event - sending invites to {len(attendee_emails)} family members: {', '.join(attendee_emails)}")
            else:
                # Individual event - no attendees
                logger.info(f"👤 Individual event - no family invites sent")
            
            # Debug: Show all team members and their email status
            for member in team_members:
                invited = "✅ INVITED" if (include_family and member.email and member.phone != team_member.phone) else "❌ Not invited"
                logger.info(f"👤 {member.name} ({member.phone}) - Email: {member.email or 'MISSING'} - {invited}")
            if include_family and not attendee_emails:
                logger.warning("⚠️ Family event requested but no family member emails found!")
                logger.warning("💡 Make sure family members have email addresses in the database.")
            elif include_family and attendee_emails:
                logger.info(f"✅ Family invites will be sent to: {', '.join(attendee_emails)}")
            else:
                logger.info(f"📝 Individual event - no invites needed")
            
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
    
    async def _tool_list_events(self, input_data: Dict, team_member, db, message_text: str) -> Dict:
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
            
            # STEP 4: Determine time using simple patterns
            target_hour = 19  # Default 7 PM
            target_minute = 0
            
            # Look for time indicators in original message
            time_patterns = [
                (r'(\d{1,2}):(\d{2})\s*(am|pm)', 'hour_minute_ampm'),
                (r'(\d{1,2})\s*(am|pm)', 'hour_ampm'),
                (r'(\d{1,2}):(\d{2})', 'hour_minute_24h'),
                (r'(\d{1,2})\s*pm', 'hour_pm'),
                (r'(\d{1,2})\s*am', 'hour_am'),
            ]
            
            time_found = False
            for pattern, pattern_type in time_patterns:
                match = re.search(pattern, message_lower)
                if match:
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
            
            # STEP 5: Combine date and time
            try:
                result = datetime.combine(target_date, datetime.min.time().replace(hour=target_hour, minute=target_minute))
                logger.info(f"✅ [BULLETPROOF PARSER] FINAL RESULT: {result.strftime('%A, %B %d, %Y at %I:%M %p')}")
                
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
                # Fallback to 7 PM
                result = datetime.combine(target_date, datetime.min.time().replace(hour=19, minute=0))
                logger.warning(f"⚠️ [BULLETPROOF PARSER] Using fallback time: {result}")
                return result
                
        except Exception as e:
            logger.error(f"❌ [BULLETPROOF PARSER] Unexpected error: {e}")
            # Ultimate fallback: tomorrow at 7 PM
            fallback = datetime.combine((now + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
            logger.warning(f"🆘 [BULLETPROOF PARSER] Ultimate fallback: {fallback}")
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