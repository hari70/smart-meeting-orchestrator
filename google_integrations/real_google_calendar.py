# real_google_calendar.py - Real Google Calendar API integration
# This replaces the mock calendar when you're ready for real integration

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

try:
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceCredentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

logger = logging.getLogger(__name__)

class RealGoogleCalendarClient:
    def __init__(self):
        self.service = None
        self.calendar_id = 'primary'  # Can be changed to specific calendar
        
        if GOOGLE_API_AVAILABLE:
            self._initialize_service()
        else:
            logger.error("❌ Google Calendar API libraries not installed")
            logger.info("💡 Install with: pip install google-api-python-client google-auth")
    
    def _initialize_service(self):
        \"\"\"Initialize Google Calendar API service\"\"\"
        try:
            # Option 1: Service Account (recommended for server apps)
            service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
            if service_account_file and os.path.exists(service_account_file):
                credentials = ServiceCredentials.from_service_account_file(
                    service_account_file,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
                self.service = build('calendar', 'v3', credentials=credentials)
                logger.info("✅ Google Calendar API initialized with service account")
                return
            
            # Option 2: OAuth2 credentials (for user accounts)
            credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
            token_file = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE")
            
            if credentials_file and token_file and os.path.exists(token_file):
                with open(token_file, 'r') as token:
                    creds_data = json.load(token)
                    credentials = Credentials.from_authorized_user_info(creds_data)
                
                self.service = build('calendar', 'v3', credentials=credentials)
                logger.info("✅ Google Calendar API initialized with OAuth2")
                return
            
            logger.warning("⚠️ Google Calendar credentials not found")
            logger.info("💡 Set up credentials using the setup guide below")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Calendar API: {e}")
    
    async def create_event(self, title: str, start_time: datetime, duration_minutes: int = 60, 
                          attendees: List[str] = None, meet_link: str = None) -> Optional[Dict]:
        \"\"\"Create real Google Calendar event\"\"\"
        
        if not self.service:
            logger.error("❌ Google Calendar service not initialized")
            return None
        
        try:
            # Prepare event data
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            event = {
                'summary': title,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/New_York',  # Adjust as needed
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'attendees': [{'email': email} for email in (attendees or [])],
                'description': f\"Created via SMS\\n{f'Meeting link: {meet_link}' if meet_link else ''}\"
            }
            
            # Add Google Meet integration if no custom link provided
            if not meet_link:
                event['conferenceData'] = {
                    'createRequest': {
                        'requestId': f\"sms_meeting_{int(start_time.timestamp())}\",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
            
            logger.info(f\"🗓️ Creating real Google Calendar event: {title}\")
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                conferenceDataVersion=1 if not meet_link else 0
            ).execute()
            
            logger.info(f\"✅ Real Google Calendar event created: {created_event.get('id')}\")
            
            # Extract Google Meet link if created
            hangout_link = created_event.get('hangoutLink')
            conference_data = created_event.get('conferenceData', {})
            meet_url = None
            
            if hangout_link:
                meet_url = hangout_link
            elif conference_data.get('entryPoints'):
                for entry in conference_data['entryPoints']:
                    if entry.get('entryPointType') == 'video':
                        meet_url = entry.get('uri')
                        break
            
            return {
                'id': created_event.get('id'),
                'title': title,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'attendees': attendees or [],
                'meet_link': meet_url or meet_link,
                'calendar_link': created_event.get('htmlLink'),
                'source': 'real_google_calendar'
            }
            
        except HttpError as e:
            logger.error(f\"❌ Google Calendar API error: {e}\")
            return None
        except Exception as e:
            logger.error(f\"❌ Error creating calendar event: {e}\")
            return None
    
    async def delete_event(self, event_id: str) -> bool:
        \"\"\"Delete real Google Calendar event\"\"\"
        
        if not self.service:
            return False
        
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f\"✅ Deleted Google Calendar event: {event_id}\")
            return True
            
        except HttpError as e:
            logger.error(f\"❌ Error deleting event: {e}\")
            return False
    
    async def list_events(self, days_ahead: int = 7, limit: int = 10) -> List[Dict]:
        \"\"\"List upcoming events from real Google Calendar\"\"\"
        
        if not self.service:
            return []
        
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=limit,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                formatted_events.append({
                    'id': event.get('id'),
                    'title': event.get('summary', 'No title'),
                    'start_time': start,
                    'meet_link': event.get('hangoutLink'),
                    'calendar_link': event.get('htmlLink')
                })
            
            return formatted_events
            
        except HttpError as e:
            logger.error(f\"❌ Error listing events: {e}\")
            return []

# Setup instructions for real Google Calendar integration
SETUP_INSTRUCTIONS = \"\"\"
🔧 REAL GOOGLE CALENDAR SETUP GUIDE

To enable real Google Calendar integration:

1. **Create Google Cloud Project**:
   - Go to https://console.cloud.google.com/
   - Create new project or select existing
   - Enable Google Calendar API

2. **Option A: Service Account (Recommended for servers)**:
   - Go to IAM & Admin > Service Accounts
   - Create service account
   - Download JSON key file
   - Set environment variable: GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/key.json
   - Share your calendar with the service account email

3. **Option B: OAuth2 (For personal use)**:
   - Go to APIs & Credentials > Credentials
   - Create OAuth 2.0 Client ID (Desktop application)
   - Download credentials.json
   - Run OAuth flow to get token.json
   - Set environment variables:
     GOOGLE_CALENDAR_CREDENTIALS_FILE=/path/to/credentials.json
     GOOGLE_CALENDAR_TOKEN_FILE=/path/to/token.json

4. **Install Dependencies**:
   pip install google-api-python-client google-auth google-auth-oauthlib

5. **Update Railway Environment**:
   ENABLE_REAL_GOOGLE_CALENDAR=true
   GOOGLE_SERVICE_ACCOUNT_FILE=/app/service-account.json

6. **Test Integration**:
   Text: "Schedule test meeting tomorrow at 3pm"
   Check your Google Calendar for real event!

📋 QUICK START (Service Account):
1. Create service account in Google Cloud Console
2. Download JSON key
3. Upload to Railway as file or environment variable
4. Share your Google Calendar with service account email
5. Set ENABLE_REAL_GOOGLE_CALENDAR=true
6. Deploy and test!
\"\"\"

if __name__ == \"__main__\":
    print(SETUP_INSTRUCTIONS)