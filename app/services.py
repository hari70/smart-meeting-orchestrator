"""Service singletons (initialized once) used across routers.

This avoids circular imports between routers and keeps construction logic
away from `main.py` for cleaner testing.
"""
import logging
from app.config import get_settings
from sms_coordinator.surge_client import SurgeSMSClient
from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
from google_integrations.meet_client import GoogleMeetClient
from app.application.command_processor import ModernCommandProcessor

settings = get_settings()
if settings.environment != 'testing':
    # Re-evaluate in case tests loaded after initial import forced test mode
    settings = get_settings(refresh=True)
logger = logging.getLogger(__name__)

# Placeholder / optional clients (kept simple to satisfy tests referencing attributes)
class _PlaceholderClient:
    def __init__(self):
        self.enabled = False

# Initialize external clients
surge_client = SurgeSMSClient(
    api_key=settings.surge_api_key or "",
    account_id=settings.surge_account_id or ""
)

# Some tests expect strava_client to be None initially (placeholder behavior)
strava_client = None

calendar_client = RealMCPCalendarClient()
logger.info("📅 Using Real MCP Google Calendar tools (your 8 tools)")

meet_client = GoogleMeetClient()
logger.info("🔗 Meet client initialized")

# NEW: Clean Architecture - Modern Command Processor
command_processor = ModernCommandProcessor(
    calendar_client=calendar_client,
    meet_client=meet_client, 
    sms_client=surge_client
)

logger.info("🤖 Modern Command Processor ready - Clean Architecture with Strategy/Command patterns")
