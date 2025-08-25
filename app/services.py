"""Service singletons (initialized once) used across routers.

This avoids circular imports between routers and keeps construction logic
away from `main.py` for cleaner testing.
"""
import logging
from app.config import get_settings
from sms_coordinator.surge_client import SurgeSMSClient
from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
from google_integrations.meet_client import GoogleMeetClient
from llm_integration.enhanced_command_processor import LLMCommandProcessor

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize external clients
surge_client = SurgeSMSClient(
    api_key=settings.surge_api_key or "",
    account_id=settings.surge_account_id or ""
)

calendar_client = DirectGoogleCalendarClient()
logger.info("🔗 Using DIRECT Google Calendar API only (MCP disabled in refactor step 1)")

meet_client = GoogleMeetClient()
strava_client = None  # Placeholder for later integration

# Command processor (LLM if enabled else fallback logic inside class)
command_processor = LLMCommandProcessor(surge_client, calendar_client, meet_client, strava_client)
