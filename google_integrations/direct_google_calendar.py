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
        # Debug: Show what environment variables are available
        logger.info(f"🔍 Checking Google Calendar environment variables...")
        
        self.access_token = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
        self.refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") 
        self.client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        # Debug logging (without exposing full tokens)
        logger.info(f"🔑 GOOGLE_CALENDAR_ACCESS_TOKEN: {'SET' if self.access_token else 'NOT SET'}")
        logger.info(f"🔑 GOOGLE_CALENDAR_REFRESH_TOKEN: {'SET' if self.refresh_token else 'NOT SET'}")
        logger.info(f"🔑 GOOGLE_CALENDAR_CLIENT_ID: {'SET' if self.client_id else 'NOT SET'}")
        logger.info(f"🔑 GOOGLE_CALENDAR_CLIENT_SECRET: {'SET' if self.client_secret else 'NOT SET'}")
        logger.info(f"🔑 GOOGLE_CALENDAR_ID: {self.calendar_id}")
        
        # Also check alternative environment variable names that might be used
        alt_vars = [
            "GOOGLE_ACCESS_TOKEN", "GOOGLE_API_KEY", "GOOGLE_OAUTH_TOKEN",
            "CALENDAR_ACCESS_TOKEN", "CALENDAR_API_KEY"
        ]
        for var in alt_vars:
            value = os.getenv(var)
            if value:
                logger.info(f"🔍 Found alternative env var {var}: SET")
        
        self.base_url = "https://www.googleapis.com/calendar/v3"
        self.enabled = bool(self.access_token or (self.refresh_token and self.client_id))
        
        if self.enabled:
            logger.info("✅ Direct Google Calendar API integration enabled")
            logger.info(f"📅 Will create REAL events in calendar: {self.calendar_id}")
        else:
            logger.info("📝 Direct Google Calendar API not configured - using mock mode")
            logger.info("💡 To enable real events, set GOOGLE_CALENDAR_ACCESS_TOKEN or (GOOGLE_CALENDAR_REFRESH_TOKEN + GOOGLE_CALENDAR_CLIENT_ID)")
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        """Create real Google Calendar event via API"""
        
        if not self.enabled:
            logger.warning("⚠️ Google Calendar API not configured - would create real event")
            return self._mock_event_response(title, start_time, duration_minutes, meet_link)
        
        try:
            # Ensure we have a valid access token
            await self._ensure_valid_token()
            
            # Double-check that client is still enabled after token validation
            if not self.enabled:
                logger.error("❌ Client disabled after token validation - falling back to mock")
                return self._mock_event_response(title, start_time, duration_minutes, meet_link)
            
            if not self.access_token:
                logger.error("❌ No access token available after validation - falling back to mock")
                return self._mock_event_response(title, start_time, duration_minutes, meet_link)
            
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
            logger.info(f"👥 Event attendees: {attendees or []}")
            
            # Call Google Calendar API
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/calendars/{self.calendar_id}/events"
            params = {"conferenceDataVersion": 1} if not meet_link else {}
            
            logger.info(f"🔗 API URL: {url}")
            logger.info(f"🔑 Using token: {self.access_token[:15]}..." if self.access_token else "No token")
            
            response = requests.post(
                url,
                headers=headers,
                json=event_data,
                params=params,
                timeout=10
            )
            
            logger.info(f"📊 API Response: {response.status_code}")
            
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
                logger.error(f"❌ Google Calendar API error: {response.status_code}")
                logger.error(f"❌ Response body: {response.text}")
                
                # Common error cases
                if response.status_code == 401:
                    logger.error("❌ Authentication failed - access token likely expired or invalid")
                elif response.status_code == 403:
                    logger.error("❌ Permission denied - check Google Calendar API permissions")
                elif response.status_code == 400:
                    logger.error("❌ Bad request - check event data format")
                    logger.error(f"❌ Event data sent: {json.dumps(event_data, indent=2)}")
                
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
        
        # If we have no access token but have refresh token, try to refresh
        if not self.access_token and self.refresh_token:
            logger.info("🔄 No access token found, attempting refresh...")
            await self._refresh_access_token()
            return
        
        # If we have an access token, test if it's valid
        if self.access_token:
            logger.info("🧪 Testing current access token validity...")
            test_url = f"{self.base_url}/calendars/primary"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            try:
                test_response = requests.get(test_url, headers=headers, timeout=5)
                
                if test_response.status_code == 200:
                    logger.info("✅ Access token is valid")
                    return
                elif test_response.status_code == 401:
                    logger.warning("⚠️ Access token expired, attempting refresh...")
                    if self.refresh_token:
                        await self._refresh_access_token()
                    else:
                        logger.error("❌ No refresh token available for token refresh")
                        self.enabled = False
                else:
                    logger.warning(f"⚠️ Token test returned {test_response.status_code}: {test_response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Error testing token validity: {e}")
        
        # Final check - if still no valid token, disable the client
        if not self.access_token:
            logger.error("❌ No valid access token available")
            self.enabled = False
    
    async def _refresh_access_token(self):
        """Refresh access token using refresh token"""
        
        if not self.refresh_token or not self.client_id or not self.client_secret:
            logger.error("❌ Missing refresh token or client credentials for refresh")
            logger.error(f"   Refresh token: {'SET' if self.refresh_token else 'MISSING'}")
            logger.error(f"   Client ID: {'SET' if self.client_id else 'MISSING'}")
            logger.error(f"   Client Secret: {'SET' if self.client_secret else 'MISSING'}")
            return
        
        try:
            logger.info("🔄 Attempting to refresh access token...")
            
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
            
            logger.info(f"🔄 Token refresh response: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                logger.info("✅ Access token refreshed successfully")
                
                # Log token info (first few chars only for security)
                if self.access_token:
                    logger.info(f"🔑 New token starts with: {self.access_token[:10]}...")
                    # Update enabled status
                    self.enabled = True
                else:
                    logger.error("❌ Refresh response missing access_token field")
                    logger.error(f"❌ Response data: {token_data}")
                    
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                logger.error(f"   Response: {response.text}")
                
                # Common error cases
                if response.status_code == 400:
                    logger.error("❌ Likely causes: Invalid refresh token, client ID/secret mismatch, or token expired")
                elif response.status_code == 401:
                    logger.error("❌ Likely cause: Invalid client credentials")
                    
                # Disable client if refresh fails
                self.enabled = False
                    
        except Exception as e:
            logger.error(f"❌ Error refreshing token: {e}")
            self.enabled = False
    
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
SETUP_INSTRUCTIONS = """
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
"""

if __name__ == "__main__":
    print(SETUP_INSTRUCTIONS)