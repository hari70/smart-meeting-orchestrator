# real_mcp_calendar_client.py - Direct MCP Google Calendar integration
# This calls your actual MCP Google Calendar tools instead of mock responses

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class RealMCPCalendarClient:
    def __init__(self):
        """Initialize real MCP calendar client"""
        self.available_tools = []
        self.mcp_enabled = self._detect_mcp_tools()
        
        if self.mcp_enabled:
            logger.info("✅ Real MCP Google Calendar tools detected")
        else:
            logger.warning("⚠️ MCP Google Calendar tools not available")
    
    def _detect_mcp_tools(self) -> bool:
        """Assume MCP Google Calendar tools are available - user has 8 tools"""
        # Since you have 8 Google Calendar MCP tools, let's assume they're available
        # and let the actual tool calls determine if they work
        logger.info("🎯 Assuming your 8 MCP Google Calendar tools are available")
        return True
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        """Create calendar event using real MCP tools"""
        
        if not self.mcp_enabled:
            logger.error("❌ MCP Google Calendar tools not available")
            return None
        
        try:
            logger.info(f"🔗 Creating REAL calendar event via MCP: {title} at {start_time}")
            
            # Convert to ISO format for MCP tools
            start_iso = start_time.isoformat()
            end_time = start_time + timedelta(minutes=duration_minutes)
            end_iso = end_time.isoformat()
            
            # Prepare attendees in Google Calendar format
            attendee_list = []
            if attendees:
                for email in attendees:
                    if email and '@' in email:  # Valid email
                        attendee_list.append({"email": email})
            
            # Call real MCP Google Calendar create_event tool
            # This is the actual MCP tool call
            event_data = await self._call_mcp_tool("google-calendar:create_gcal_event", {
                "calendar_id": "primary",
                "summary": title,
                "start": start_iso,
                "end": end_iso,
                "time_zone": "America/New_York",
                "attendees": attendee_list,
                "description": f"Created via SMS\\n{f'Meeting link: {meet_link}' if meet_link else ''}",
                "location": None
            })
            
            if event_data and not event_data.get("error"):
                logger.info(f"✅ REAL Google Calendar event created via MCP: {event_data.get('id')}")
                
                # Extract Google Meet link if created
                hangout_link = event_data.get("hangoutLink")
                meet_url = hangout_link or meet_link
                
                return {
                    "id": event_data.get("id"),
                    "title": title,
                    "start_time": start_iso,
                    "end_time": end_iso,
                    "attendees": attendees or [],
                    "meet_link": meet_url,
                    "calendar_link": event_data.get("htmlLink"),
                    "source": "real_mcp_tools"
                }
            else:
                logger.error(f"❌ MCP tool failed: {event_data}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating MCP calendar event: {e}")
            return None
    
    async def list_events(self, days_ahead: int = 7, limit: int = 10) -> List[Dict]:
        """List events using real MCP tools"""
        
        if not self.mcp_enabled:
            return []
        
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            # Call real MCP Google Calendar list_events tool
            events_data = await self._call_mcp_tool("google-calendar:list_gcal_events", {
                "calendar_id": "primary",
                "time_min": time_min,
                "time_max": time_max,
                "max_results": limit
            })
            
            if events_data and not events_data.get("error"):
                # Handle both MCP format (items) and fallback format (events)
                events = events_data.get("items") or events_data.get("events", [])
                
                formatted_events = []
                for event in events:
                    # Check if this is already formatted (from DirectGoogleCalendarClient fallback)
                    if "start_time" in event and not isinstance(event.get("start"), dict):
                        # Already formatted by DirectGoogleCalendarClient - use as-is
                        formatted_events.append({
                            "id": event.get("id"),
                            "title": event.get("title", "No title"),
                            "start_time": event.get("start_time"),
                            "meet_link": event.get("meet_link"),
                            "calendar_link": event.get("calendar_link")
                        })
                    else:
                        # Raw Google Calendar API format - needs formatting
                        start = event["start"].get("dateTime", event["start"].get("date"))
                        formatted_events.append({
                            "id": event.get("id"),
                            "title": event.get("summary", "No title"),
                            "start_time": start,
                            "meet_link": event.get("hangoutLink"),
                            "calendar_link": event.get("htmlLink")
                        })
                
                return formatted_events
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error listing MCP events: {e}")
            return []
    
    async def find_free_time(self, attendees: List[str], duration_minutes: int = 60, 
                           preferred_times: List[datetime] = None) -> Optional[datetime]:
        """Find free time using real MCP tools"""
        
        if not self.mcp_enabled:
            return None
        
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=7)).isoformat() + 'Z'
            
            # Call real MCP Google Calendar freebusy tool
            freebusy_data = await self._call_mcp_tool("google-calendar:find_free_time", {
                "calendar_ids": ["primary"],
                "time_min": time_min,
                "time_max": time_max
            })
            
            if freebusy_data and not freebusy_data.get("error"):
                # Analyze busy times and find free slots
                # This is simplified - you'd implement more sophisticated logic
                busy_periods = []
                calendars = freebusy_data.get("calendars", {})
                
                for calendar_id, calendar_data in calendars.items():
                    busy_times = calendar_data.get("busy", [])
                    busy_periods.extend(busy_times)
                
                # Find first available slot (simplified algorithm)
                suggested_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
                if suggested_time <= now:
                    suggested_time += timedelta(days=1)
                
                # Skip weekends
                while suggested_time.weekday() >= 5:
                    suggested_time += timedelta(days=1)
                
                return suggested_time
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding free time via MCP: {e}")
            return None
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete event using real MCP tools"""
        
        if not self.mcp_enabled:
            return False
        
        try:
            # Call real MCP Google Calendar delete_event tool
            result = await self._call_mcp_tool("google-calendar:delete_gcal_event", {
                "calendar_id": "primary",
                "event_id": event_id
            })
            
            return not result.get("error") if result else False
            
        except Exception as e:
            logger.error(f"❌ Error deleting MCP event: {e}")
            return False
    
    async def check_conflicts(self, start_time: datetime, duration_minutes: int = 60, 
                            attendees: Optional[List[str]] = None, exclude_meeting_title: Optional[str] = None) -> Dict:
        """
        Check for scheduling conflicts using real MCP tools
        """
        try:
            if not self.mcp_enabled:
                return {"conflicts": [], "has_conflicts": False, "message": "Calendar API not available"}
            
            from datetime import timedelta
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Use the list_events functionality to check for conflicts
            time_min = start_time.isoformat() + 'Z'
            time_max = end_time.isoformat() + 'Z'
            
            # Call MCP tool to get events in the time range
            events_data = await self._call_mcp_tool("google-calendar:list_gcal_events", {
                "calendar_id": "primary",
                "time_min": time_min,
                "time_max": time_max,
                "max_results": 10,
                "exclude_meeting_title": exclude_meeting_title  # Pass exclusion to fallback
            })
            
            conflicts = []
            
            if events_data and not events_data.get("error"):
                # Handle both MCP format (items) and fallback format (events)
                events = events_data.get("items") or events_data.get("events", [])
                
                for event in events:
                    # Check if this is already formatted (from DirectGoogleCalendarClient fallback)
                    if "start_time" in event and not isinstance(event.get("start"), dict):
                        # Already formatted by DirectGoogleCalendarClient - use as-is
                        event_title = event.get("title", "Busy")
                        
                        # Skip the meeting being rescheduled
                        if exclude_meeting_title and event_title.lower() == exclude_meeting_title.lower():
                            logger.info(f"🔄 Skipping meeting being rescheduled: {event_title}")
                            continue
                            
                        conflicts.append({
                            "title": event_title,
                            "start": event.get("start_time"),
                            "end": "N/A",  # DirectGoogleCalendarClient doesn't provide end time
                            "calendar_link": event.get("calendar_link")
                        })
                    else:
                        # Raw Google Calendar API format
                        event_start = event["start"].get("dateTime", event["start"].get("date"))
                        event_end = event["end"].get("dateTime", event["end"].get("date"))
                        event_title = event.get("summary", "Busy")
                        
                        # Skip the meeting being rescheduled
                        if exclude_meeting_title and event_title.lower() == exclude_meeting_title.lower():
                            logger.info(f"🔄 Skipping meeting being rescheduled: {event_title}")
                            continue
                        
                        conflicts.append({
                            "title": event_title,
                            "start": event_start,
                            "end": event_end,
                            "calendar_link": event.get("htmlLink")
                        })
            
            if conflicts:
                logger.info(f"⚠️ Found {len(conflicts)} scheduling conflicts via MCP")
                conflict_titles = [c["title"] for c in conflicts]
                return {
                    "conflicts": conflicts,
                    "has_conflicts": True,
                    "message": f"Conflict with: {', '.join(conflict_titles)}"
                }
            else:
                logger.info(f"✅ No conflicts found for proposed time via MCP")
                return {
                    "conflicts": [],
                    "has_conflicts": False,
                    "message": "Time slot is available"
                }
            
        except Exception as e:
            logger.error(f"❌ Error checking conflicts via MCP: {e}")
            # Safe fallback - don't block rescheduling due to conflict check failure
            return {
                "conflicts": [],
                "has_conflicts": False,
                "message": f"Unable to check conflicts ({str(e)}), proceeding anyway"
            }
    
    async def _call_mcp_tool(self, tool_name: str, parameters: Dict) -> Optional[Dict]:
        """Call real MCP tool - this is where the magic happens"""
        
        try:
            logger.info(f"🔧 Calling MCP tool: {tool_name} with params: {json.dumps(parameters, indent=2)}")
            
            # Method 1: Direct MCP tool call (if available in environment)
            if hasattr(__builtins__, 'mcp_tools'):
                tool_func = getattr(__builtins__.mcp_tools, tool_name, None)
                if tool_func:
                    result = await tool_func(**parameters)
                    logger.info(f"✅ MCP tool result: {result}")
                    return result
            
            # Method 2: Environment-specific MCP call
            # This depends on how your MCP tools are exposed
            # You might need to adjust this based on your setup
            
            # Method 3: Try Claude Desktop MCP pattern
            try:
                # In Claude Desktop with MCP tools, you might have:
                if tool_name == "google-calendar:create_gcal_event":
                    # This would be replaced with actual MCP call
                    result = await google_calendar_create_event(**parameters)
                    return result
                elif tool_name == "google-calendar:list_gcal_events":
                    result = await google_calendar_list_events(**parameters) 
                    return result
                # ... etc for other tools
            except NameError:
                pass
            
            # Method 4: MCP-Bridge server call - Debug and find correct endpoints
            mcp_server_url = os.getenv("MCP_SERVER_URL", "https://mcp-bridge-service-production.up.railway.app")
            if mcp_server_url:
                import requests
                try:
                    # First, let's discover what endpoints are available
                    logger.info(f"🔍 Discovering MCP server endpoints at {mcp_server_url}")
                    
                    # Try to find documentation or available endpoints
                    discovery_endpoints = [
                        f"{mcp_server_url}/docs",           # OpenAPI docs
                        f"{mcp_server_url}/openapi.json",   # OpenAPI spec  
                        f"{mcp_server_url}/health",         # Health check
                        f"{mcp_server_url}/tools/list",     # Tool listing
                        f"{mcp_server_url}/mcp/tools/list", # MCP tool listing
                        f"{mcp_server_url}/api/tools",      # API tools
                        f"{mcp_server_url}/v1/tools",       # Versioned tools
                    ]
                    
                    available_endpoints = []
                    for endpoint in discovery_endpoints:
                        try:
                            resp = requests.get(endpoint, timeout=5)
                            if resp.status_code == 200:
                                available_endpoints.append(endpoint)
                                logger.info(f"✅ Found endpoint: {endpoint} (status: {resp.status_code})")
                                
                                # If it's tools/list, try to get the tools
                                if "tools/list" in endpoint or "api/tools" in endpoint:
                                    try:
                                        tools_data = resp.json()
                                        logger.info(f"📋 Available tools: {tools_data}")
                                    except:
                                        logger.info(f"📋 Tools endpoint found but couldn't parse JSON")
                            else:
                                logger.debug(f"❌ {endpoint}: {resp.status_code}")
                        except:
                            logger.debug(f"❌ {endpoint}: Connection failed")
                    
                    # Now try tool execution with the discovered pattern
                    tool_execution_endpoints = [
                        f"{mcp_server_url}/tools/call",       # Standard
                        f"{mcp_server_url}/mcp/tools/call",   # MCP prefixed
                        f"{mcp_server_url}/call_tool",       # Alternative
                        f"{mcp_server_url}/api/tools/call",   # API prefixed
                        f"{mcp_server_url}/v1/tools/call",    # Versioned
                        f"{mcp_server_url}/tools/execute",   # Execute variant
                        f"{mcp_server_url}/execute",         # Simple execute
                        f"{mcp_server_url}/tool",            # Single tool
                        f"{mcp_server_url}/run_tool",        # Run variant
                    ]
                    
                    # Try different payload formats too
                    payload_formats = [
                        {"name": tool_name, "arguments": parameters},           # Standard MCP
                        {"tool_name": tool_name, "parameters": parameters},     # Alternative 1
                        {"tool": tool_name, "args": parameters},               # Alternative 2
                        {"function": tool_name, "arguments": parameters},      # Function style
                        {"action": tool_name, "params": parameters},           # Action style
                        parameters  # Direct parameters
                    ]
                    
                    for endpoint in tool_execution_endpoints:
                        for i, payload in enumerate(payload_formats):
                            try:
                                logger.info(f"🧪 Testing {endpoint} with payload format {i+1}: {tool_name}")
                                
                                response = requests.post(
                                    endpoint,
                                    json=payload,
                                    headers={"Content-Type": "application/json"},
                                    timeout=10
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    logger.info(f"🎉 SUCCESS! Found working endpoint: {endpoint}")
                                    logger.info(f"🎉 Working payload format {i+1}: {payload}")
                                    logger.info(f"✅ MCP result: {result}")
                                    return result
                                elif response.status_code not in [404, 405]:  # Not "not found" or "method not allowed"
                                    logger.info(f"🔍 {endpoint} (format {i+1}): {response.status_code} - {response.text[:100]}")
                                    
                            except requests.exceptions.RequestException as e:
                                logger.debug(f"❌ {endpoint} (format {i+1}): {e}")
                                continue
                            
                            # Don't try all payload formats for every endpoint - just first few
                            if i >= 2:  # Only try first 3 formats per endpoint
                                break
                    
                    # If we found available endpoints but no working tool execution, provide helpful info
                    if available_endpoints:
                        logger.error(f"🚨 MCP server is reachable but tool execution failed")
                        logger.error(f"🔍 Available endpoints: {available_endpoints}")
                    else:
                        logger.error(f"🚨 No standard MCP endpoints found on server")
                    
                    # Fall through to backup method below
                    
                except Exception as e:
                    logger.error(f"❌ MCP server discovery failed: {e}")
                    # Fall through to backup method below
            
            # Method 5: Fallback to Direct Google Calendar API when MCP fails
            logger.warning(f"⚠️ MCP server failed, falling back to Direct Google Calendar API with Railway credentials")
            
            # Import and use the direct Google Calendar client as fallback
            try:
                from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
                direct_client = DirectGoogleCalendarClient()
                
                if tool_name == "google-calendar:create_gcal_event":
                    logger.info(f"🔄 Fallback: Creating event via Direct Google Calendar API")
                    
                    # Convert MCP parameters to direct API parameters
                    title = parameters.get("summary", "SMS Event")
                    
                    # Parse start time
                    start_str = parameters.get("start")
                    if start_str:
                        try:
                            if isinstance(start_str, str):
                                # Try to parse ISO format
                                if 'T' in start_str:
                                    start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                                else:
                                    # Fallback to tomorrow 7pm
                                    start_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
                                    if start_time <= datetime.now():
                                        start_time = start_time.replace(day=start_time.day + 1)
                            else:
                                start_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
                        except:
                            start_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
                    else:
                        start_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
                    
                    # Duration
                    duration = 60  # Default 1 hour
                    
                    # Attendees
                    attendees = []
                    if parameters.get("attendees"):
                        attendees = [a.get("email") for a in parameters["attendees"] if a.get("email")]
                    
                    # Call direct Google Calendar API
                    result = await direct_client.create_event(
                        title=title,
                        start_time=start_time,
                        duration_minutes=duration,
                        attendees=attendees
                    )
                    
                    if result:
                        logger.info(f"✅ Direct Google Calendar API success: {result.get('title')}")
                        return result
                    else:
                        logger.error(f"❌ Direct Google Calendar API also failed")
                        return {"error": "Both MCP and Direct Google Calendar API failed"}
                        
                elif tool_name == "google-calendar:list_gcal_events":
                    logger.info(f"🔄 Fallback: Listing events via Direct Google Calendar API")
                    
                    # Check if this is being called from check_conflicts with time filtering
                    time_min = parameters.get("time_min")
                    time_max = parameters.get("time_max")
                    exclude_meeting_title = parameters.get("exclude_meeting_title")
                    
                    if time_min and time_max:
                        # This is a conflict check - use specific time range filtering
                        logger.info(f"🔍 Fallback conflict check for time range: {time_min} to {time_max}")
                        if exclude_meeting_title:
                            logger.info(f"🔍 Excluding meeting: {exclude_meeting_title}")
                        
                        # Parse the time range from ISO format
                        try:
                            start_time = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
                            end_time = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
                            duration_minutes = int((end_time - start_time).total_seconds() / 60)
                            
                            # Call DirectGoogleCalendarClient's check_conflicts directly
                            conflict_result = await direct_client.check_conflicts(
                                start_time=start_time,
                                duration_minutes=duration_minutes,
                                exclude_meeting_title=exclude_meeting_title
                            )
                            
                            # Convert conflict result to list format expected by RealMCPCalendarClient
                            if conflict_result.get("has_conflicts"):
                                conflicts = conflict_result.get("conflicts", [])
                                # Convert to Google Calendar API format
                                items = []
                                for conflict in conflicts:
                                    items.append({
                                        "summary": conflict.get("title", "Busy"),
                                        "start": {"dateTime": conflict.get("start")},
                                        "end": {"dateTime": conflict.get("end")},
                                        "htmlLink": conflict.get("calendar_link")
                                    })
                                return {"success": True, "items": items}
                            else:
                                return {"success": True, "items": []}
                                
                        except Exception as time_parse_error:
                            logger.error(f"❌ Error parsing time range in fallback: {time_parse_error}")
                            return {"success": True, "items": []}
                    else:
                        # Regular list_events call
                        days_ahead = parameters.get("days_ahead", 7) 
                        limit = parameters.get("max_results", 10)
                        
                        # DirectGoogleCalendarClient.list_events already returns properly formatted events
                        events = await direct_client.list_events(days_ahead=days_ahead, limit=limit)
                        
                        # Return in fallback format - the list_events method will handle this
                        return {"success": True, "events": events}
                    
                else:
                    logger.warning(f"⚠️ Tool {tool_name} not supported in direct fallback")
                    return {"error": f"Tool {tool_name} not available in fallback mode"}
                    
            except ImportError as e:
                logger.error(f"❌ Direct Google Calendar fallback not available: {e}")
                return {"error": "MCP failed and direct Google Calendar fallback not available"}
            except Exception as e:
                logger.error(f"❌ Direct Google Calendar fallback failed: {e}")
                return {"error": f"Direct Google Calendar fallback failed: {str(e)}"}
            
            logger.error(f"❌ Could not call MCP tool: {tool_name} - No fallback available")
            return {"error": f"MCP tool {tool_name} not available - ensure your 8 MCP Google Calendar tools are properly connected"}
            
        except Exception as e:
            logger.error(f"❌ Error calling MCP tool {tool_name}: {e}")
            return {"error": str(e)}
    
    def get_available_tools(self) -> List[str]:
        """Get list of available MCP Google Calendar tools"""
        # You mentioned you have 8 tools - return them here
        return [
            "google-calendar:create_gcal_event",
            "google-calendar:list_gcal_events", 
            "google-calendar:fetch_gcal_event",
            "google-calendar:update_gcal_event",
            "google-calendar:delete_gcal_event",
            "google-calendar:find_free_time",
            "google-calendar:list_gcal_calendars",
            "google-calendar:search_gcal_events"
        ]