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
from datetime import datetime, timedelta
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
        import pytz
        et_tz = pytz.timezone('US/Eastern')
        current_time_et = datetime.now(et_tz).strftime('%A, %B %d, %Y at %I:%M %p ET')
        user_timezone = context.get('timezone', 'US/Eastern')
        
        return f"""You are an intelligent meeting coordinator for {user.name}.

CURRENT CONTEXT:
- Date/Time: {current_time_et}
- User: {user.name}
- Team: {context.get('team_name', 'Family')}

YOUR ROLE:
You coordinate meetings through SMS using REAL Google Calendar MCP tools.

CRITICAL WORKFLOW:
1. For scheduling requests → Use parse_time_expression first, then google-calendar:create_gcal_event
2. For calendar questions → Use google-calendar:list_gcal_events
3. For finding meetings → Use google-calendar:search_gcal_events
4. For moving meetings → Use google-calendar:search_gcal_events to find, then google-calendar:update_gcal_event
5. For canceling meetings → Use google-calendar:search_gcal_events to find, then google-calendar:delete_gcal_event
6. For timezone confusion → Use ask_for_clarification but PRESERVE context

TOOL USAGE RULES:
- ALWAYS use parse_time_expression before creating/updating events
- When searching for meetings, use the meeting title as the search query
- For rescheduling: search → get event_id → update with new time
- Pass calendar_id="primary" for all Google Calendar tools
- Use time_zone="America/New_York" as default

CONTEXT AWARENESS:
- If user says "how about 2pm" after trying to reschedule, they mean reschedule the SAME meeting
- If user says "move it to X" they mean the meeting from the previous message
- Don't ask "what meeting" if context is clear from conversation

TIMEZONE HANDLING:
- If time zone is ambiguous (like "4pm"), ask: "Do you mean 4pm Eastern Time?"
- But REMEMBER what they're trying to schedule and complete it once clarified
- Always include timezone in time expressions when parsing

EXAMPLE WORKFLOWS:

Create Meeting:
1. parse_time_expression("tomorrow at 4pm ET", 60)
2. google-calendar:create_gcal_event with parsed ISO times

Reschedule Meeting:
1. google-calendar:search_gcal_events("AI Talk")
2. parse_time_expression("Friday at 3pm ET", 60) 
3. google-calendar:update_gcal_event with event_id and new times

List Events:
1. Calculate time_min/time_max in ISO format
2. google-calendar:list_gcal_events with time range

RESPONSE STYLE:
- Direct and helpful
- Use tools to take action
- Keep responses under 160 characters when possible (SMS)
- Don't just respond conversationally - USE THE TOOLS!"""

    def _get_mcp_tools(self) -> List[Dict]:
        """
        Define REAL MCP Google Calendar tools for Claude to use directly
        
        These map to your actual 8 MCP Google Calendar tools
        """
        return [
            {
                "name": "google-calendar:create_gcal_event",
                "description": "Create a Google Calendar event with Google Meet link",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "summary": {
                            "type": "string", 
                            "description": "Meeting title/subject"
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in ISO format (e.g., '2025-08-29T15:00:00-04:00')"
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in ISO format (e.g., '2025-08-29T16:00:00-04:00')"
                        },
                        "time_zone": {
                            "type": "string",
                            "description": "Timezone",
                            "default": "America/New_York"
                        },
                        "attendees": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"}
                                }
                            },
                            "description": "List of attendee email objects"
                        },
                        "description": {
                            "type": "string",
                            "description": "Meeting description"
                        }
                    },
                    "required": ["summary", "start", "end"]
                }
            },
            {
                "name": "google-calendar:list_gcal_events",
                "description": "List Google Calendar events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "time_min": {
                            "type": "string",
                            "description": "Minimum time (ISO format with Z)"
                        },
                        "time_max": {
                            "type": "string",
                            "description": "Maximum time (ISO format with Z)"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events",
                            "default": 10
                        }
                    },
                    "required": ["calendar_id"]
                }
            },
            {
                "name": "google-calendar:update_gcal_event",
                "description": "Update an existing Google Calendar event",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "event_id": {
                            "type": "string",
                            "description": "Event ID to update"
                        },
                        "summary": {
                            "type": "string",
                            "description": "New meeting title"
                        },
                        "start": {
                            "type": "string",
                            "description": "New start time in ISO format"
                        },
                        "end": {
                            "type": "string",
                            "description": "New end time in ISO format"
                        },
                        "time_zone": {
                            "type": "string",
                            "description": "Timezone",
                            "default": "America/New_York"
                        }
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "google-calendar:delete_gcal_event",
                "description": "Delete a Google Calendar event",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "event_id": {
                            "type": "string",
                            "description": "Event ID to delete"
                        }
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "google-calendar:fetch_gcal_event",
                "description": "Get details of a specific Google Calendar event",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "event_id": {
                            "type": "string",
                            "description": "Event ID to fetch"
                        }
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "google-calendar:search_gcal_events",
                "description": "Search for Google Calendar events by query",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "calendar_id": {
                            "type": "string",
                            "description": "Calendar ID",
                            "default": "primary"
                        },
                        "q": {
                            "type": "string",
                            "description": "Search query (event title, description, etc.)"
                        },
                        "time_min": {
                            "type": "string",
                            "description": "Minimum time (ISO format with Z)"
                        },
                        "time_max": {
                            "type": "string",
                            "description": "Maximum time (ISO format with Z)"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events",
                            "default": 10
                        }
                    },
                    "required": ["q"]
                }
            },
            {
                "name": "parse_time_expression",
                "description": "Helper tool to parse natural language time expressions into ISO format",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "time_expression": {
                            "type": "string",
                            "description": "Natural language time (e.g., 'tomorrow at 4pm ET', 'Friday at 3pm')"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration in minutes for end time calculation",
                            "default": 60
                        }
                    },
                    "required": ["time_expression"]
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
        Execute REAL MCP Google Calendar tools directly
        
        No more wrapper logic - direct MCP tool execution
        """
        try:
            # Parse time expressions first if needed
            if tool_name == "parse_time_expression":
                return await self._tool_parse_time(tool_input)
                
            # Ask for clarification
            elif tool_name == "ask_for_clarification":
                return await self._tool_ask_clarification(tool_input, user, db)
            
            # All Google Calendar MCP tools - delegate to calendar client
            elif tool_name.startswith("google-calendar:"):
                return await self._execute_mcp_tool(tool_name, tool_input)
                
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} failed: {e}")
            return {"success": False, "error": str(e)"}
    
    async def _execute_mcp_tool(self, tool_name: str, tool_input: Dict) -> Dict:
        """
        Execute real MCP Google Calendar tools via the calendar client
        """
        try:
            logger.info(f"🔧 Executing real MCP tool: {tool_name}")
            
            # Use the RealMCPCalendarClient to execute the tool
            result = await self.calendar_client._call_mcp_tool(tool_name, tool_input)
            
            if result and not result.get("error"):
                # Format success response based on tool type
                if tool_name == "google-calendar:create_gcal_event":
                    title = result.get("summary", "Meeting")
                    start_time = result.get("start", {}).get("dateTime", "")
                    meet_link = result.get("hangoutLink", "")
                    
                    # Parse and format the time
                    if start_time:
                        try:
                            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            formatted_time = dt.strftime('%A at %I:%M %p ET')
                        except:
                            formatted_time = start_time
                    else:
                        formatted_time = "scheduled"
                    
                    meet_text = f" Meet: {meet_link}" if meet_link else ""
                    message = f"✅ {title} scheduled for {formatted_time}!{meet_text}"
                    
                elif tool_name == "google-calendar:list_gcal_events":
                    events = result.get("items", []) or result.get("events", [])
                    if not events:
                        message = "📅 No meetings found"
                    else:
                        event_list = []
                        for event in events[:5]:  # Limit for SMS
                            title = event.get("summary", event.get("title", "Meeting"))
                            start = event.get("start", {})
                            start_time = start.get("dateTime") if isinstance(start, dict) else event.get("start_time")
                            
                            if start_time:
                                try:
                                    if isinstance(start_time, str) and 'T' in start_time:
                                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                        time_str = dt.strftime('%a %m/%d %I:%M%p')
                                    else:
                                        time_str = str(start_time)
                                except:
                                    time_str = str(start_time)
                            else:
                                time_str = "TBD"
                            
                            event_list.append(f"• {title} - {time_str}")
                        
                        message = f"📅 Upcoming meetings:\n{chr(10).join(event_list)}"
                
                elif tool_name == "google-calendar:update_gcal_event":
                    title = result.get("summary", "Meeting")
                    message = f"✅ {title} has been rescheduled!"
                    
                elif tool_name == "google-calendar:delete_gcal_event":
                    message = "✅ Meeting canceled"
                    
                elif tool_name == "google-calendar:search_gcal_events":
                    events = result.get("items", [])
                    if not events:
                        message = "🔍 No matching meetings found"
                    else:
                        # Return the events for use in next step
                        return {
                            "success": True,
                            "message": f"Found {len(events)} matching events",
                            "events": events
                        }
                        
                else:
                    # Generic success for other tools
                    message = f"✅ {tool_name.replace('google-calendar:', '').replace('_', ' ').title()} completed"
                
                return {
                    "success": True,
                    "message": message,
                    "data": result
                }
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response"
                return {
                    "success": False,
                    "error": f"MCP tool failed: {error_msg}"
                }
                
        except Exception as e:
            logger.error(f"❌ MCP tool execution failed: {e}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    async def _tool_parse_time(self, input_data: Dict) -> Dict:
        """
        Parse natural language time expressions into ISO format
        """
        try:
            time_expression = input_data["time_expression"]
            duration_minutes = input_data.get("duration_minutes", 60)
            
            # Use our existing time parsing logic
            start_time = await self._parse_when(time_expression)
            
            if not start_time:
                return {
                    "success": False,
                    "error": f"Could not parse time expression: {time_expression}"
                }
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            return {
                "success": True,
                "message": f"Parsed '{time_expression}' as {start_time.strftime('%A, %B %d at %I:%M %p ET')}",
                "start_iso": start_time.isoformat(),
                "end_iso": end_time.isoformat(),
                "start_time": start_time,
                "end_time": end_time
            }
            
        except Exception as e:
            logger.error(f"❌ Time parsing failed: {e}")
            return {
                "success": False,
                "error": f"Time parsing failed: {str(e)}"
            }
    
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
            return {"success": False, "error": "Failed to ask clarification"}
    
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
    
    async def _tool_reschedule_meeting(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Reschedule an existing meeting to a new date/time
        """
        try:
            meeting_identifier = input_data["meeting_identifier"]
            new_when = input_data["new_when"]
            new_duration = input_data.get("duration_minutes")
            
            # Find the meeting to reschedule
            meeting = await self._find_meeting_by_identifier(meeting_identifier, user, db)
            if not meeting:
                return {
                    "success": False,
                    "error": f"Couldn't find meeting matching '{meeting_identifier}'. Try being more specific."
                }
            
            # Parse new time
            new_start_time = await self._parse_when(new_when)
            if not new_start_time:
                return {
                    "success": False,
                    "error": f"Couldn't understand new time '{new_when}'. Try 'Friday at 2pm ET'"
                }
            
            # Check for conflicts at new time (excluding the meeting being rescheduled)
            duration = new_duration or meeting.duration_minutes or 60
            conflicts = await self.calendar_client.check_conflicts(
                start_time=new_start_time,
                duration_minutes=duration,
                exclude_meeting_title=meeting.title  # CRITICAL: Exclude the meeting being moved
            )
            
            # Check for conflicts - calendar client will exclude the meeting being rescheduled
            if conflicts.get("has_conflicts"):
                conflict_list = conflicts.get("conflicts", [])
                conflict_names = [c.get("title", "Meeting") for c in conflict_list]
                return {
                    "success": False,
                    "error": f"❌ Conflict at new time with: {', '.join(conflict_names)}. Choose a different time."
                }
            
            # Update the meeting using MCP tools
            if meeting.google_calendar_event_id:  # type: ignore
                # Use the real MCP update tool
                updated = await self.calendar_client._call_mcp_tool("google-calendar:update_gcal_event", {
                    "calendar_id": "primary",
                    "event_id": meeting.google_calendar_event_id,
                    "start": new_start_time.isoformat(),
                    "end": (new_start_time + timedelta(minutes=duration)).isoformat()
                })
                
                if updated and updated.get("error"):
                    return {
                        "success": False,
                        "error": f"Failed to update calendar: {updated.get('error')}"
                    }
            
            # Update database
            meeting.scheduled_time = new_start_time  # type: ignore
            if new_duration:
                meeting.duration_minutes = new_duration  # type: ignore
            db.commit()
            
            return {
                "success": True,
                "message": f"✅ '{meeting.title}' moved to {new_start_time.strftime('%A at %I:%M %p ET')}"
            }
            
        except Exception as e:
            logger.error(f"❌ Reschedule meeting failed: {e}")
            return {"success": False, "error": f"Failed to reschedule meeting: {str(e)}"}
    
    async def _tool_cancel_meeting(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Cancel an existing meeting
        """
        try:
            meeting_identifier = input_data["meeting_identifier"]
            reason = input_data.get("reason", "")
            
            # Find the meeting to cancel
            meeting = await self._find_meeting_by_identifier(meeting_identifier, user, db)
            if not meeting:
                return {
                    "success": False,
                    "error": f"Couldn't find meeting matching '{meeting_identifier}'. Try being more specific."
                }
            
            # Cancel in Google Calendar using MCP tools
            if meeting.google_calendar_event_id:  # type: ignore
                deleted = await self.calendar_client._call_mcp_tool("google-calendar:delete_gcal_event", {
                    "calendar_id": "primary",
                    "event_id": meeting.google_calendar_event_id
                })
                
                if deleted and deleted.get("error"):
                    return {
                        "success": False,
                        "error": f"Failed to cancel in calendar: {deleted.get('error')}"
                    }
            
            # Remove from database
            db.delete(meeting)
            db.commit()
            
            reason_text = f" (Reason: {reason})" if reason else ""
            
            return {
                "success": True,
                "message": f"✅ '{meeting.title}' cancelled{reason_text}"
            }
            
        except Exception as e:
            logger.error(f"❌ Cancel meeting failed: {e}")
            return {"success": False, "error": f"Failed to cancel meeting: {str(e)}"}
    
    async def _tool_update_meeting(self, input_data: Dict, user, db: Session) -> Dict:
        """
        Update meeting details (title, attendees, description)
        """
        try:
            meeting_identifier = input_data["meeting_identifier"]
            new_title = input_data.get("new_title")
            add_attendees = input_data.get("add_attendees", [])
            remove_attendees = input_data.get("remove_attendees", [])
            new_description = input_data.get("new_description")
            
            # Find the meeting to update
            meeting = await self._find_meeting_by_identifier(meeting_identifier, user, db)
            if not meeting:
                return {
                    "success": False,
                    "error": f"Couldn't find meeting matching '{meeting_identifier}'. Try being more specific."
                }
            
            # Update database fields
            changes = []
            if new_title:
                meeting.title = new_title
                changes.append(f"title → '{new_title}'")
            
            if new_description:
                meeting.description = new_description
                changes.append("description updated")
            
            # Handle attendees (simplified for now)
            if add_attendees or remove_attendees:
                changes.append("attendees updated")
            
            # Update Google Calendar if needed
            if meeting.google_calendar_event_id and (new_title or new_description):  # type: ignore
                await self.calendar_client.update_event(
                    event_id=meeting.google_calendar_event_id,
                    title=new_title or meeting.title,
                    description=new_description or meeting.description
                )
            
            db.commit()
            
            changes_text = ", ".join(changes)
            
            return {
                "success": True,
                "message": f"✅ '{meeting.title}' updated: {changes_text}"
            }
            
        except Exception as e:
            logger.error(f"❌ Update meeting failed: {e}")
            return {"success": False, "error": f"Failed to update meeting: {str(e)}"}
    
    # ===============================
    # HELPER METHODS (Keep Simple)
    # ===============================
    
    async def _parse_when(self, when_text: str) -> Optional[datetime]:
        """
        Robust, timezone-aware time parsing - FINAL SOLUTION
        
        Handles: 'tomorrow at 4pm ET', 'Friday at 2pm', '4pm', 'today at 11am'
        Always returns timezone-aware datetime in Eastern Time
        """
        try:
            import pytz
            import re
            from dateutil import parser
            
            when_lower = when_text.lower().strip()
            
            # ALWAYS use Eastern Time as the default timezone
            et_tz = pytz.timezone('US/Eastern')
            now_et = datetime.now(et_tz)
            
            logger.info(f"🕐 Parsing time: '{when_text}' (current ET time: {now_et.strftime('%Y-%m-%d %H:%M %Z')})")
            
            # Step 1: Determine the base date (timezone-aware)
            base_date = None
            
            if "tomorrow" in when_lower:
                base_date = (now_et + timedelta(days=1)).date()
                logger.info(f"📅 Base date: tomorrow = {base_date}")
            elif "today" in when_lower:
                base_date = now_et.date()
                logger.info(f"📅 Base date: today = {base_date}")
            elif any(day in when_lower for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
                # Find next occurrence of the specified day
                days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                target_day = None
                for i, day in enumerate(days_of_week):
                    if day in when_lower:
                        target_day = i
                        break
                
                if target_day is not None:
                    current_weekday = now_et.weekday()
                    days_ahead = (target_day - current_weekday) % 7
                    if days_ahead == 0:  # Same day
                        days_ahead = 7 if "next" in when_lower else 0
                    
                    base_date = (now_et + timedelta(days=days_ahead)).date()
                    logger.info(f"📅 Base date: {days_of_week[target_day]} = {base_date}")
            else:
                # Try to parse absolute date or default to today
                try:
                    parsed = parser.parse(when_text, fuzzy=True)
                    if parsed.tzinfo is None:
                        # Make it timezone-aware in ET
                        parsed = et_tz.localize(parsed)
                    else:
                        # Convert to ET
                        parsed = parsed.astimezone(et_tz)
                    logger.info(f"📅 Parsed absolute date: {parsed}")
                    return parsed
                except:
                    base_date = now_et.date()
                    logger.info(f"📅 Base date: default to today = {base_date}")
            
            # Step 2: Extract time with timezone support
            hour = None
            minute = 0
            
            # Enhanced time patterns with timezone support
            time_patterns = [
                r'(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)(?:\s*(et|est|edt|pt|pst|pdt|ct|cst|cdt|mt|mst|mdt))?',
                r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)(?:\s*(et|est|edt|pt|pst|pdt|ct|cst|cdt|mt|mst|mdt))?',
                r'(\d{1,2}):(\d{2})(?:\s*(et|est|edt|pt|pst|pdt|ct|cst|cdt|mt|mst|mdt))?',
            ]
            
            time_match = None
            for pattern in time_patterns:
                time_match = re.search(pattern, when_lower)
                if time_match:
                    break
            
            if time_match:
                hour = int(time_match.group(1))
                
                # Handle minutes (might be None for patterns without minutes)
                if len(time_match.groups()) >= 2 and time_match.group(2) and time_match.group(2).isdigit():
                    minute = int(time_match.group(2))
                
                # Handle AM/PM
                ampm = None
                timezone_abbr = None
                
                for group in time_match.groups()[1:]:
                    if group and group.lower() in ['am', 'pm', 'a.m.', 'p.m.']:
                        ampm = group
                    elif group and group.lower() in ['et', 'est', 'edt', 'pt', 'pst', 'pdt', 'ct', 'cst', 'cdt', 'mt', 'mst', 'mdt']:
                        timezone_abbr = group
                
                # Convert to 24-hour format
                if ampm and 'p' in ampm.lower() and hour != 12:
                    hour += 12
                elif ampm and 'a' in ampm.lower() and hour == 12:
                    hour = 0
                
                logger.info(f"🕐 Extracted time: {hour:02d}:{minute:02d} {ampm or ''} {timezone_abbr or ''}")
            else:
                logger.warning(f"⚠️ Could not extract time from '{when_text}'")
                return None
            
            # Step 3: Create timezone-aware datetime
            if base_date and hour is not None:
                # Create naive datetime first
                naive_dt = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
                
                # Make it timezone-aware in Eastern Time (default)
                result_dt = et_tz.localize(naive_dt)
                
                # TODO: Handle other timezones when specified
                # For now, always assume/convert to Eastern Time
                
                logger.info(f"✅ Final parsed time: {result_dt.strftime('%A, %B %d at %I:%M %p %Z')}")
                return result_dt
            
            logger.warning(f"⚠️ Could not parse '{when_text}' - missing date or time components")
            return None
            
        except Exception as e:
            logger.error(f"❌ Time parsing failed for '{when_text}': {e}")
            return None
    
    async def _find_meeting_by_identifier(self, identifier: str, user, db: Session):
        """
        Find a meeting by title or partial match
        """
        try:
            from database.models import Meeting
            
            # First try exact title match
            meeting = db.query(Meeting).filter(
                Meeting.team_id == user.team_id,
                Meeting.title.ilike(f"%{identifier}%")
            ).order_by(Meeting.scheduled_time.desc()).first()
            
            return meeting
            
        except Exception as e:
            logger.warning(f"⚠️ Meeting lookup failed: {e}")
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
                    context["conversation_history"] = recent[-5:]  # Last 5 messages for better context
            
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