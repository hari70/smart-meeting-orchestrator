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
        """Create real Google Calendar event via API with improved token handling"""
        
        if not self.enabled:
            return self._mock_event_response(title, start_time, duration_minutes, meet_link)
        
        try:
            # IMPROVED: Try to ensure we have a working token, but be more aggressive about it
            logger.info("🔄 Ensuring valid access token for calendar creation...")
            
            # If we don't have an access token, or if it's likely expired, refresh immediately
            if not self.access_token or len(self.access_token) < 50:
                logger.info("🔄 No access token or token looks invalid, refreshing...")
                if not await self._refresh_access_token():
                    logger.error("❌ Could not refresh access token")
                    return self._mock_event_response(title, start_time, duration_minutes, meet_link)
            
            # Test the token with a simple API call
            if not await self._test_token_with_retry():
                logger.error("❌ Token validation failed even after refresh")
                return self._mock_event_response(title, start_time, duration_minutes, meet_link)
            
            logger.info("✅ Token validation successful, proceeding with real calendar creation...")
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Handle timezone awareness - convert naive datetime to timezone-aware
            if start_time.tzinfo is None:
                from datetime import timezone as dt_timezone
                import time
                # Get system timezone offset
                local_offset = time.timezone if not time.daylight else time.altzone
                local_tz_offset = timedelta(seconds=-local_offset)
                start_time = start_time.replace(tzinfo=dt_timezone(local_tz_offset))
                end_time = end_time.replace(tzinfo=dt_timezone(local_tz_offset))
                logger.info(f"🕐 Converted to timezone-aware: {start_time.isoformat()}")
            
            # Determine timezone string for Google Calendar
            # For now, use Eastern Time but this should be user-configurable
            calendar_timezone = "America/New_York"  # TODO: Make configurable per user
            
            # Prepare event data
            event_data = {
                "summary": title,
                "description": f"Created via SMS\\n{f'Meeting link: {meet_link}' if meet_link else ''}",
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": calendar_timezone
                },
                "end": {
                    "dateTime": end_time.isoformat(), 
                    "timeZone": calendar_timezone
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
            
            logger.info(f"📅 Creating REAL Google Calendar event: {title}")
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
            
            logger.info(f"🌐 Making API call to: {url}")
            logger.info(f"🔑 Using access token: {self.access_token[:20]}...")
            
            response = requests.post(
                url,
                headers=headers,
                json=event_data,
                params=params,
                timeout=15
            )
            
            logger.info(f"📡 API Response status: {response.status_code}")
            
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
                    # Try ONE more refresh and retry
                    if await self._refresh_access_token():
                        logger.info("🔄 Token refreshed, retrying event creation ONE more time...")
                        # Update headers with new token
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        response = requests.post(url, headers=headers, json=event_data, params=params, timeout=15)
                        if response.status_code in [200, 201]:
                            event_result = response.json()
                            logger.info(f"✅ REAL Google Calendar event created on retry: {event_result.get('id')}")
                            hangout_link = event_result.get("hangoutLink")
                            return {
                                "id": event_result.get("id"),
                                "title": title,
                                "start_time": start_time.isoformat(),
                                "end_time": end_time.isoformat(),
                                "attendees": attendees or [],
                                "meet_link": hangout_link or meet_link,
                                "calendar_link": event_result.get("htmlLink"),
                                "source": "real_google_api"
                            }
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
    
    async def check_conflicts(self, start_time: datetime, duration_minutes: int = 60, attendees: List[str] = None) -> Dict:
        """Check for scheduling conflicts for proposed meeting time"""
        
        if not self.enabled:
            return {"conflicts": [], "has_conflicts": False, "message": "Calendar API not available"}
        
        try:
            if not await self._ensure_valid_token():
                return {"conflicts": [], "has_conflicts": False, "message": "Calendar authentication failed"}
            
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            # Query for events during the proposed time
            time_min = start_time.isoformat() + 'Z'
            time_max = end_time.isoformat() + 'Z'
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": True,
                "orderBy": "startTime"
            }
            
            logger.info(f"🔍 Checking conflicts for {start_time.strftime('%A, %B %d at %I:%M %p')}")
            
            response = requests.get(
                f"{self.base_url}/calendars/{self.calendar_id}/events",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                events_data = response.json()
                events = events_data.get("items", [])
                
                conflicts = []
                for event in events:
                    event_start = event["start"].get("dateTime", event["start"].get("date"))
                    event_end = event["end"].get("dateTime", event["end"].get("date"))
                    
                    conflicts.append({
                        "title": event.get("summary", "Busy"),
                        "start": event_start,
                        "end": event_end,
                        "calendar_link": event.get("htmlLink")
                    })
                
                if conflicts:
                    logger.info(f"⚠️ Found {len(conflicts)} scheduling conflicts")
                    conflict_titles = [c["title"] for c in conflicts]
                    return {
                        "conflicts": conflicts,
                        "has_conflicts": True,
                        "message": f"Conflict with: {', '.join(conflict_titles)}"
                    }
                else:
                    logger.info(f"✅ No conflicts found for proposed time")
                    return {
                        "conflicts": [],
                        "has_conflicts": False,
                        "message": "Time slot is available"
                    }
            
            else:
                logger.error(f"❌ Failed to check conflicts: {response.status_code}")
                return {"conflicts": [], "has_conflicts": False, "message": "Unable to check calendar"}
            
        except Exception as e:
            logger.error(f"❌ Error checking conflicts: {e}")
            return {"conflicts": [], "has_conflicts": False, "message": f"Error: {str(e)}"}
    
    async def find_free_time(self, duration_minutes: int = 60, days_ahead: int = 7, preferred_hours: List[int] = None) -> Optional[datetime]:
        """Find next available free time slot"""
        
        if not self.enabled:
            # Return mock suggestion
            return datetime.now() + timedelta(hours=2)
        
        try:
            if not await self._ensure_valid_token():
                return None
            
            preferred_hours = preferred_hours or [9, 10, 11, 14, 15, 16, 17, 18, 19]  # Business hours + evening
            
            # Check each day for availability
            for day_offset in range(days_ahead):
                check_date = datetime.now() + timedelta(days=day_offset)
                
                # Skip past times for today
                start_hour = max(preferred_hours[0], datetime.now().hour + 1) if day_offset == 0 else preferred_hours[0]
                
                for hour in preferred_hours:
                    if hour < start_hour:
                        continue
                    
                    proposed_time = check_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                    
                    # Check for conflicts
                    conflict_check = await self.check_conflicts(proposed_time, duration_minutes)
                    
                    if not conflict_check["has_conflicts"]:
                        logger.info(f"✅ Found free time: {proposed_time.strftime('%A, %B %d at %I:%M %p')}")
                        return proposed_time
            
            logger.warning(f"⚠️ No free time found in next {days_ahead} days")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding free time: {e}")
            return None
    
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
    
    async def _test_token_with_retry(self) -> bool:
        """Test token validity with retry logic"""
        
        try:
            test_url = f"{self.base_url}/calendars/primary"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(test_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Token validation successful")
                return True
            elif response.status_code == 401:
                logger.warning("⚠️ Access token expired, attempting refresh...")
                if await self._refresh_access_token():
                    # Test again with new token
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    response = requests.get(test_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        logger.info("✅ Token validation successful after refresh")
                        return True
                    else:
                        logger.error(f"❌ Token still invalid after refresh: {response.status_code}")
                        return False
                else:
                    logger.error("❌ Failed to refresh token")
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
                    logger.info(f"🔑 New token: {self.access_token[:20]}...")
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
