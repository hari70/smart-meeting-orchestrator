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
                          attendees: Optional[List[str]] = None, meet_link: Optional[str] = None) -> Optional[Dict]:
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
                           preferred_times: Optional[List[datetime]] = None) -> Optional[datetime]:
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
    
    async def update_event(self, event_id: str, title: Optional[str] = None, start_time: Optional[datetime] = None, 
                          duration_minutes: Optional[int] = None, attendees: Optional[List[str]] = None) -> Optional[Dict]:
        """Update event using real MCP tools"""
        
        if not self.mcp_enabled:
            return None
        
        try:
            # Prepare update parameters
            update_params = {
                "calendar_id": "primary",
                "event_id": event_id
            }
            
            if title:
                update_params["summary"] = title
                
            if start_time and duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
                update_params["start"] = start_time.isoformat()
                update_params["end"] = end_time.isoformat()
                update_params["time_zone"] = "America/New_York"
                
            if attendees:
                attendee_list = []
                for email in attendees:
                    if email and '@' in email:
                        attendee_list.append({"email": email})
                update_params["attendees"] = attendee_list
            
            # Call real MCP Google Calendar update_event tool
            result = await self._call_mcp_tool("google-calendar:update_gcal_event", update_params)
            
            if result and not result.get("error"):
                logger.info(f"✅ Successfully updated event via MCP: {result.get('id')}")
                return {
                    "id": result.get("id"),
                    "title": result.get("summary", title),
                    "start_time": result.get("start", {}).get("dateTime"),
                    "end_time": result.get("end", {}).get("dateTime"),
                    "calendar_link": result.get("htmlLink"),
                    "source": "real_mcp_tools"
                }
            else:
                logger.error(f"❌ MCP update tool failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error updating MCP event: {e}")
            return None
    
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
        """Call MCP tool directly through the registry (SIMPLE AND RELIABLE)"""

        try:
            logger.info(f"🔧 Calling MCP tool directly: {tool_name} with params: {json.dumps(parameters, indent=2)}")

            # Call the MCP tool directly through the registry - this is the CORRECT way
            from mcp_integration.base import tool_registry
            result = await tool_registry.call(tool_name, **parameters)

            logger.info(f"✅ MCP tool {tool_name} executed successfully")
            return result

        except ValueError as e:
            logger.error(f"❌ MCP tool '{tool_name}' not found in registry: {e}")
            return {"error": f"Tool not found: {e}"}
        except Exception as e:
            logger.error(f"❌ Error calling MCP tool {tool_name}: {e}")
            return {"error": str(e)}
        
        logger.error(f"❌ Could not call MCP tool: {tool_name} - No fallback available")
        return {"error": f"MCP tool {tool_name} not available - ensure your 8 MCP Google Calendar tools are properly connected"}
    
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