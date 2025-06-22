# direct_google_calendar.py - Direct Google Calendar API integration for Railway
# This bypasses MCP and calls Google Calendar API directly

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
import base64

logger = logging.getLogger(__name__)

class DirectGoogleCalendarClient:
    def __init__(self):
        """Initialize direct Google Calendar API client"""
        self.access_token = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
        self.refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") 
        self.client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        self.base_url = "https://www.googleapis.com/calendar/v3"
        self.enabled = bool(self.access_token or (self.refresh_token and self.client_id))
        
        if self.enabled:
            logger.info("✅ Direct Google Calendar API integration enabled")
        else:
            logger.info("📝 Direct Google Calendar API not configured - using mock mode")
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        """Create real Google Calendar event via API"""
        
        if not self.enabled:
            logger.warning("⚠️ Google Calendar API not configured - would create real event")
            return self._mock_event_response(title, start_time, duration_minutes, meet_link)
        
        try:
            # Ensure we have a valid access token
            await self._ensure_valid_token()
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Prepare event data
            event_data = {
                "summary": title,
                "description": f"Created via SMS\\n{f'Meeting link: {meet_link}' if meet_link else ''}",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "America/New_York"
                },
                "end": {
                    "dateTime": end_time.isoformat(), 
                    "timeZone": "America/New_York"
                },
                "attendees": [{"email": email} for email in (attendees or [])],
                "reminders": {
                    "useDefault": True
                }
            }
            
            # Add Google Meet if no custom link
            if not meet_link:
                event_data["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"sms_{int(start_time.timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"}
                    }
                }
            
            logger.info(f"🗓️ Creating REAL Google Calendar event: {title} at {start_time}")
            
            # Call Google Calendar API
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/calendars/{self.calendar_id}/events"
            params = {"conferenceDataVersion": 1} if not meet_link else {}
            
            response = requests.post(
                url,
                headers=headers,
                json=event_data,
                params=params,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                event_result = response.json()
                logger.info(f"✅ REAL Google Calendar event created: {event_result.get('id')}")
                
                # Extract Google Meet link
                hangout_link = event_result.get("hangoutLink")
                conference_data = event_result.get("conferenceData", {})
                meet_url = hangout_link or meet_link
                
                if not meet_url and conference_data.get("entryPoints"):
                    for entry in conference_data["entryPoints"]:
                        if entry.get("entryPointType") == "video":
                            meet_url = entry.get("uri")
                            break
                
                return {
                    "id": event_result.get("id"),
                    "title": title,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "attendees": attendees or [],
                    "meet_link": meet_url,
                    "calendar_link": event_result.get("htmlLink"),
                    "source": "real_google_api"
                }
            else:
                logger.error(f"❌ Google Calendar API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating Google Calendar event: {e}")
            return None
    
    async def list_events(self, days_ahead: int = 7, limit: int = 10) -> List[Dict]:
        """List upcoming events from Google Calendar"""
        
        if not self.enabled:
            return []
        
        try:
            await self._ensure_valid_token()
            
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": limit,
                "singleEvents": True,
                "orderBy": "startTime"
            }
            
            response = requests.get(
                f"{self.base_url}/calendars/{self.calendar_id}/events",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                events_data = response.json()
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
            logger.error(f"❌ Error listing Google Calendar events: {e}")
            return []
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete Google Calendar event"""
        
        if not self.enabled:
            return True  # Mock success
        
        try:
            await self._ensure_valid_token()
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.delete(
                f"{self.base_url}/calendars/{self.calendar_id}/events/{event_id}",
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 204
            
        except Exception as e:
            logger.error(f"❌ Error deleting Google Calendar event: {e}")
            return False
    
    async def _ensure_valid_token(self):
        """Ensure we have a valid access token"""
        
        if not self.access_token and self.refresh_token:
            await self._refresh_access_token()
        
        # TODO: Add token expiry check and refresh logic
        # For now, assume token is valid
    
    async def _refresh_access_token(self):
        """Refresh access token using refresh token"""
        
        if not self.refresh_token or not self.client_id or not self.client_secret:
            logger.error("❌ Missing refresh token or client credentials")
            return
        
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                logger.info("✅ Access token refreshed")
            else:
                logger.error(f"❌ Token refresh failed: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Error refreshing token: {e}")
    
    def _mock_event_response(self, title: str, start_time: datetime, duration_minutes: int, meet_link: str) -> Dict:
        """Return mock response when API not configured"""
        
        logger.warning(f"⚠️ [WOULD CREATE REAL EVENT] {title} at {start_time}")
        logger.info("💡 To enable real Google Calendar events, set up Google Calendar API credentials")
        
        return {
            "id": f"would_create_{int(start_time.timestamp())}",
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=duration_minutes)).isoformat(),
            "attendees": [],
            "meet_link": meet_link,
            "calendar_link": f"https://calendar.google.com/calendar/u/0/r/day/{start_time.strftime('%Y/%m/%d')}",
            "source": "would_be_real_google_api",
            "warning": "WOULD CREATE REAL EVENT - Set up Google Calendar API credentials"
        }

# Quick setup instructions
SETUP_INSTRUCTIONS = \"\"\"
🚀 QUICK GOOGLE CALENDAR API SETUP

To create REAL calendar events (bypassing MCP):

1. **Get Google Calendar API Credentials**:
   - Go to https://console.cloud.google.com/
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials
   - Download credentials.json

2. **Get Access Token** (one-time setup):
   - Use Google OAuth playground: https://developers.google.com/oauthplayground/
   - Authorize Google Calendar API v3
   - Get access_token and refresh_token

3. **Add to Railway Environment**:
   GOOGLE_CALENDAR_ACCESS_TOKEN=ya29.your_access_token_here
   GOOGLE_CALENDAR_REFRESH_TOKEN=your_refresh_token_here  
   GOOGLE_CALENDAR_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CALENDAR_CLIENT_SECRET=your_client_secret
   USE_DIRECT_GOOGLE_CALENDAR=true

4. **Test**:
   Text: "Schedule family dinner tomorrow at 7pm"
   Result: REAL Google Calendar event created!

⚡ FASTER OPTION: Use existing OAuth tokens from your local setup
\"\"\"

if __name__ == "__main__":
    print(SETUP_INSTRUCTIONS)