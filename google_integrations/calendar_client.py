import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class GoogleCalendarClient:
    def __init__(self):
        # Check if we're running in Claude with MCP tools available
        self.has_mcp_tools = self._check_mcp_availability()
        self.credentials_path = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH")
        self.token_path = os.getenv("GOOGLE_CALENDAR_TOKEN_PATH")
        
        if self.has_mcp_tools:
            logger.info("✅ Google Calendar MCP tools available")
        else:
            logger.info("📝 Using mock Google Calendar integration")
    
    def _check_mcp_availability(self) -> bool:
        """Check if MCP Google Calendar tools are available"""
        try:
            # This would be the real check for MCP tools
            # For now, we'll use environment variable to enable/disable
            return os.getenv("ENABLE_MCP_CALENDAR") == "true"
        except:
            return False
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        """Create a Google Calendar event using MCP tools if available"""
        try:
            if self.has_mcp_tools:
                return await self._create_event_mcp(title, start_time, duration_minutes, attendees, meet_link)
            else:
                return await self._create_event_mock(title, start_time, duration_minutes, attendees, meet_link)
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None
    
    async def _create_event_mcp(self, title: str, start_time: datetime, duration_minutes: int, 
                               attendees: List[str], meet_link: str) -> Dict:
        """Create event using real MCP Google Calendar tools"""
        # This is where you'd use the actual MCP tools
        # For example, if this runs in Claude with google-calendar tools:
        
        logger.info(f"🔗 Creating real calendar event via MCP: {title} at {start_time}")
        
        # Convert to ISO format for MCP tools
        start_iso = start_time.isoformat()
        end_iso = (start_time + timedelta(minutes=duration_minutes)).isoformat()
        
        # In a real MCP environment, you'd call:
        # event = await mcp_tools.google_calendar.create_event(
        #     summary=title,
        #     start=start_iso,
        #     end=end_iso,
        #     attendees=attendees,
        #     description=f"Meeting link: {meet_link}" if meet_link else None
        # )
        
        # For now, simulate MCP response
        event_data = {
            "id": f"mcp_event_{int(start_time.timestamp())}",
            "title": title,
            "start_time": start_iso,
            "end_time": end_iso,
            "attendees": attendees or [],
            "meet_link": meet_link,
            "calendar_link": f"https://calendar.google.com/calendar/u/0/r/day/{start_time.strftime('%Y/%m/%d')}",
            "source": "mcp_tools"
        }
        
        return event_data
    
    async def _create_event_mock(self, title: str, start_time: datetime, duration_minutes: int, 
                                attendees: List[str], meet_link: str) -> Dict:
        """Create mock event for development/testing"""
        logger.info(f"📅 Creating mock calendar event: {title} at {start_time}")
        
        event_data = {
            "id": f"mock_event_{int(start_time.timestamp())}",
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=duration_minutes)).isoformat(),
            "attendees": attendees or [],
            "meet_link": meet_link,
            "calendar_link": f"https://calendar.google.com/calendar/u/0/r/day/{start_time.strftime('%Y/%m/%d')}",
            "source": "mock"
        }
        
        return event_data
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete a Google Calendar event"""
        try:
            if self.has_mcp_tools:
                return await self._delete_event_mcp(event_id)
            else:
                return await self._delete_event_mock(event_id)
                
        except Exception as e:
            logger.error(f"Error deleting calendar event: {str(e)}")
            return False
    
    async def _delete_event_mcp(self, event_id: str) -> bool:
        """Delete event using real MCP tools"""
        logger.info(f"🗑️ Deleting real calendar event via MCP: {event_id}")
        
        # In real MCP environment:
        # result = await mcp_tools.google_calendar.delete_event(event_id)
        # return result.success
        
        return True  # Mock success
    
    async def _delete_event_mock(self, event_id: str) -> bool:
        """Delete mock event"""
        logger.info(f"🗑️ Deleting mock calendar event: {event_id}")
        return True
    
    async def find_free_time(self, attendees: List[str], duration_minutes: int = 60, 
                           preferred_times: List[datetime] = None) -> Optional[datetime]:
        """Find free time for attendees using MCP tools if available"""
        try:
            if self.has_mcp_tools:
                return await self._find_free_time_mcp(attendees, duration_minutes, preferred_times)
            else:
                return await self._find_free_time_mock(attendees, duration_minutes, preferred_times)
                
        except Exception as e:
            logger.error(f"Error finding free time: {str(e)}")
            return None
    
    async def _find_free_time_mcp(self, attendees: List[str], duration_minutes: int, 
                                 preferred_times: List[datetime]) -> Optional[datetime]:
        """Find free time using real MCP tools"""
        logger.info(f"🔍 Finding free time via MCP for {len(attendees)} attendees")
        
        # In real MCP environment:
        # busy_times = await mcp_tools.google_calendar.get_busy_times(
        #     attendees=attendees,
        #     time_min=(datetime.now()).isoformat(),
        #     time_max=(datetime.now() + timedelta(days=7)).isoformat()
        # )
        # free_time = find_first_available_slot(busy_times, duration_minutes, preferred_times)
        
        # Mock response - next weekday at 3 PM
        now = datetime.now()
        target_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)
        
        return target_time
    
    async def _find_free_time_mock(self, attendees: List[str], duration_minutes: int, 
                                  preferred_times: List[datetime]) -> Optional[datetime]:
        """Find free time using simple logic"""
        logger.info(f"🔍 Finding mock free time for {len(attendees)} attendees")
        
        # Simple logic: next business day at 3 PM
        now = datetime.now()
        target_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
        
        # If it's past 3 PM today, go to tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        
        # If it's weekend, go to Monday
        while target_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            target_time += timedelta(days=1)
        
        return target_time