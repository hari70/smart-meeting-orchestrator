# direct_google_calendar.py - FIXED GOOGLE CALENDAR INTEGRATION
# Fixed credential handling, token refresh, and simplified logging

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
        """Initialize direct Google Calendar API client with improved credential handling"""
        
        # Load credentials from environment
        self.access_token = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
        self.refresh_token = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") 
        self.client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        # API configuration
        self.base_url = "https://www.googleapis.com/calendar/v3"
        self.oauth_url = "https://oauth2.googleapis.com/token"
        
        # Determine if client is enabled
        self.enabled = self._check_credentials()
        
        if self.enabled:
            logger.info("✅ Google Calendar API integration enabled")
            logger.info(f"📅 Calendar ID: {self.calendar_id}")
            if not self.access_token and self.refresh_token:
                logger.info("🔄 Will refresh access token on first use")
        else:
            logger.warning("⚠️ Google Calendar API not configured - using mock mode")
            logger.info("💡 Set GOOGLE_CALENDAR_ACCESS_TOKEN or (GOOGLE_CALENDAR_REFRESH_TOKEN + GOOGLE_CALENDAR_CLIENT_ID + GOOGLE_CALENDAR_CLIENT_SECRET)")
    
    def _check_credentials(self) -> bool:
        """Check if we have valid credentials"""
        
        # Option 1: Direct access token
        if self.access_token:
            logger.info("🔑 Access token provided")
            return True
        
        # Option 2: Refresh token with OAuth credentials
        if self.refresh_token and self.client_id and self.client_secret:
            logger.info("🔑 Refresh token + OAuth credentials provided")
            
            # Validate format
            if not self.client_id.endswith('.apps.googleusercontent.com'):
                logger.error("❌ Invalid client_id format - should end with .apps.googleusercontent.com")
                return False
            
            if not self.refresh_token.startswith('1//'):
                logger.warning("⚠️ Refresh token doesn't start with '1//' - may be invalid")
            
            return True
        
        # No valid credentials
        return False
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        """Create real Google Calendar event via API"""
        
        if not self.enabled:
            return self._mock_event_response(title, start_time, duration_minutes, meet_link)
        
        try:
            # Ensure we have a valid access token
            if not await self._ensure_valid_token():
                logger.error("❌ Could not obtain valid access token")
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
            
            logger.info(f"📅 Creating Google Calendar event: {title}")
            logger.info(f"⏰ Time: {start_time.strftime('%A, %B %d at %I:%M %p')}")
            if attendees:
                logger.info(f"👥 Attendees: {', '.join(attendees)}")
            
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
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                event_result = response.json()
                logger.info(f"✅ Google Calendar event created: {event_result.get('id')}")
                
                # Extract Google Meet link
                hangout_link = event_result.get("hangoutLink")
                conference_data = event_result.get("conferenceData", {})
                meet_url = hangout_link or meet_link
                
                if not meet_url and conference_data.get("entryPoints"):
                    for entry in conference_data["entryPoints"]:
                        if entry.get("entryPointType") == "video":
                            meet_url = entry.get("uri")
                            break
                
                # Log successful attendee invites
                actual_attendees = event_result.get('attendees', [])
                if actual_attendees:
                    logger.info(f"📧 Invites sent to {len(actual_attendees)} attendees")
                
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
                error_detail = response.text[:200] if response.text else "No error details"
                logger.error(f"❌ Error details: {error_detail}")
                
                # Handle specific error cases
                if response.status_code == 401:
                    logger.error("❌ Authentication failed - token expired or invalid")
                    # Try to refresh token once
                    if await self._refresh_access_token():
                        logger.info("🔄 Token refreshed, retrying event creation...")
                        return await self.create_event(title, start_time, duration_minutes, attendees, meet_link)
                elif response.status_code == 403:
                    logger.error("❌ Permission denied - check Google Calendar API permissions")
                elif response.status_code == 400:
                    logger.error("❌ Bad request - check event data format")
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating Google Calendar event: {e}")
            return None
    
    async def list_events(self, days_ahead: int = 7, limit: int = 10) -> List[Dict]:
        """List upcoming events from Google Calendar"""
        
        if not self.enabled:
            return []
        
        try:
            if not await self._ensure_valid_token():
                return []
            
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
                
                logger.info(f"📋 Retrieved {len(formatted_events)} events from Google Calendar")
                return formatted_events
            
            else:
                logger.error(f"❌ Failed to list events: {response.status_code}")
                return []
            
        except Exception as e:
            logger.error(f"❌ Error listing Google Calendar events: {e}")
            return []
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete Google Calendar event"""
        
        if not self.enabled:
            return True  # Mock success
        
        try:
            if not await self._ensure_valid_token():
                return False
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.delete(
                f"{self.base_url}/calendars/{self.calendar_id}/events/{event_id}",
                headers=headers,
                timeout=10
            )
            
            success = response.status_code == 204
            if success:
                logger.info(f"✅ Deleted Google Calendar event: {event_id}")
            else:
                logger.error(f"❌ Failed to delete event: {response.status_code}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error deleting Google Calendar event: {e}")
            return False
    
    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        
        # If we have an access token, test if it's valid
        if self.access_token:
            if await self._test_token_validity():
                return True
            else:
                logger.warning("⚠️ Access token invalid, attempting refresh...")
                return await self._refresh_access_token()
        
        # If no access token but have refresh credentials, try to refresh
        if self.refresh_token and self.client_id and self.client_secret:
            logger.info("🔄 No access token, attempting to refresh...")
            return await self._refresh_access_token()
        
        logger.error("❌ No valid credentials available")
        return False
    
    async def _test_token_validity(self) -> bool:
        """Test if the current access token is valid"""
        
        try:
            test_url = f"{self.base_url}/calendars/primary"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(test_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                logger.warning("⚠️ Access token expired")
                return False
            else:
                logger.warning(f"⚠️ Token test returned {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error testing token validity: {e}")
            return False
    
    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        
        if not self.refresh_token or not self.client_id or not self.client_secret:
            logger.error("❌ Missing refresh credentials")
            return False
        
        try:
            logger.info("🔄 Refreshing access token...")
            
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(
                self.oauth_url,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                
                if self.access_token:
                    logger.info("✅ Access token refreshed successfully")
                    return True
                else:
                    logger.error("❌ Refresh response missing access_token")
                    return False
                    
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                
                # Parse error details
                try:
                    error_data = response.json()
                    error_type = error_data.get('error', 'unknown')
                    logger.error(f"❌ Error type: {error_type}")
                    
                    if error_type == 'invalid_grant':
                        logger.error("❌ Refresh token expired - need to re-authorize")
                    elif error_type == 'unauthorized_client':
                        logger.error("❌ Invalid client credentials")
                except:
                    logger.error(f"❌ Response: {response.text[:100]}")
                
                return False
                    
        except Exception as e:
            logger.error(f"❌ Error refreshing token: {e}")
            return False
    
    def _mock_event_response(self, title: str, start_time: datetime, duration_minutes: int, meet_link: str) -> Dict:
        """Return mock response when API not configured"""
        
        logger.info(f"📝 [MOCK MODE] Would create: {title} at {start_time.strftime('%A, %B %d at %I:%M %p')}")
        
        return {
            "id": f"mock_{int(start_time.timestamp())}",
            "title": title,
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=duration_minutes)).isoformat(),
            "attendees": [],
            "meet_link": meet_link or "https://meet.google.com/mock-link",
            "calendar_link": f"https://calendar.google.com/calendar/u/0/r/day/{start_time.strftime('%Y/%m/%d')}",
            "source": "mock",
            "note": "MOCK EVENT - Configure Google Calendar API for real events"
        }

# Configuration helper for quick setup
def print_setup_guide():
    """Print quick setup guide for Google Calendar integration"""
    print("""
🚀 GOOGLE CALENDAR QUICK SETUP

Method 1: OAuth2 Flow (Recommended)
1. Go to: https://console.cloud.google.com/
2. Create project + Enable Google Calendar API
3. Create OAuth 2.0 credentials (Web application)
4. Add redirect URI: https://developers.google.com/oauthplayground
5. Go to: https://developers.google.com/oauthplayground/
6. Select "Google Calendar API v3" scope
7. Authorize and get refresh_token

Method 2: Service Account
1. Create service account in Google Cloud Console
2. Download JSON key file
3. Share your calendar with service account email

Railway Environment Variables:
GOOGLE_CALENDAR_REFRESH_TOKEN=1//your_refresh_token
GOOGLE_CALENDAR_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CALENDAR_CLIENT_SECRET=your_client_secret

Test:
curl -X POST https://your-app.railway.app/test/create-calendar-event \\
  -H "Content-Type: application/json" \\
  -d '{"title": "Test Event", "hours_from_now": 2}'
""")

if __name__ == "__main__":
    print_setup_guide()
