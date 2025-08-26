"""Service singletons (initialized once) used across routers.

This avoids circular imports between routers and keeps construction logic
away from `main.py` for cleaner testing.
"""
import logging
from app.config import get_settings
from sms_coordinator.surge_client import SurgeSMSClient
from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
from google_integrations.meet_client import GoogleMeetClient
from llm_integration.intelligent_coordinator import IntelligentCoordinator

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize external clients
surge_client = SurgeSMSClient(
    api_key=settings.surge_api_key or "",
    account_id=settings.surge_account_id or ""
)

calendar_client = DirectGoogleCalendarClient()
logger.info("📅 Using Direct Google Calendar API")

meet_client = GoogleMeetClient()
logger.info("🔗 Meet client initialized")

# NEW: Clean Architecture - AI-First Coordinator
command_processor = IntelligentCoordinator(
    calendar_client=calendar_client,
    meet_client=meet_client, 
    sms_client=surge_client
)

logger.info("🤖 Intelligent Coordinator ready - SMS → LLM → MCP Tools architecture")
