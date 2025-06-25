# direct_google_calendar_fixed.py - FIXED TOKEN HANDLING
# Fixed the token validation logic that was causing mock mode

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

logger = logging.getLogger(__name__)

class DirectGoogleCalendarClientFixed:
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
        else:
            logger.warning("⚠️ Google Calendar API not configured - using mock mode")
    
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
                try:
                    error_data = response.json()
                    logger.error(f"❌ Error details: {error_data}")
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
