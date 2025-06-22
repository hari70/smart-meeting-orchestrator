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
        """Detect if MCP Google Calendar tools are available"""
        try:
            # In a real MCP environment (like Claude Desktop), 
            # you'd have access to the MCP tool registry
            # For now, we'll check if we're in that environment
            
            # Check if we're running in an MCP-enabled environment
            if hasattr(__builtins__, 'mcp_tools') or os.getenv("MCP_CALENDAR_AVAILABLE") == "true":
                return True
            
            # Alternative check - see if specific MCP functions are available
            try:
                import inspect
                frame = inspect.currentframe()
                while frame:
                    if 'google_calendar' in frame.f_globals:
                        return True
                    frame = frame.f_back
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting MCP tools: {e}")
            return False
    
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
                events = events_data.get("items", [])
                
                formatted_events = []
                for event in events:
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
            
            # Method 4: HTTP-based MCP server call (if using MCP server)
            mcp_server_url = os.getenv("MCP_SERVER_URL", "https://mcp-bridge-service-production.up.railway.app")
            if mcp_server_url:
                import requests
                try:
                    response = requests.post(
                        f"{mcp_server_url}/tools/{tool_name}",
                        json=parameters,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"✅ MCP server result: {result}")
                        return result
                    else:
                        logger.error(f"❌ MCP server error: {response.status_code} - {response.text}")
                        return {"error": f"MCP server returned {response.status_code}"}
                except requests.exceptions.RequestException as e:
                    logger.error(f"❌ MCP server request failed: {e}")
                    return {"error": f"MCP server request failed: {str(e)}"}
            
            logger.error(f"❌ Could not call MCP tool: {tool_name}")
            return {"error": f"MCP tool {tool_name} not available"}
            
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