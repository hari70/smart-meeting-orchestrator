"""Service singletons (initialized once) used across routers.

This avoids circular imports between routers and keeps construction logic
away from `main.py` for cleaner testing.
"""
import logging
from typing import Optional, List, Dict
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
    
    # MCP processor interface methods
    async def create_meeting(self, title: str) -> Optional[str]:
        """Placeholder: Return None for failed meet client"""
        return None
    
    async def create_event(self, title: str, start_time, duration_minutes: int = 60, 
                          attendees: Optional[List[str]] = None, meet_link: Optional[str] = None) -> Optional[Dict]:
        """Placeholder: Return None for failed calendar client"""
        return None
    
    async def list_events(self, start_date, end_date) -> List[Dict]:
        """Placeholder: Return empty list for failed calendar client"""
        return []
    
    async def find_free_time(self, duration_minutes: int, date) -> List[Dict]:
        """Placeholder: Return empty list for failed calendar client"""
        return []
    
    async def send_message(self, *args, **kwargs):
        """Placeholder: Do nothing for failed SMS client"""
        pass

# Initialize external clients
try:
    surge_client = SurgeSMSClient(
        api_key=settings.surge_api_key or "",
        account_id=settings.surge_account_id or ""
    )
    logger.info("📱 Surge SMS client initialized")
except Exception as e:
    logger.warning(f"⚠️  Failed to initialize Surge SMS client: {e}")
    surge_client = _PlaceholderClient()

try:
    calendar_client = RealMCPCalendarClient()
    logger.info("📅 Using Real MCP Google Calendar tools (your 8 tools)")
except Exception as e:
    logger.warning(f"⚠️  Failed to initialize MCP Calendar client: {e}")
    calendar_client = _PlaceholderClient()

try:
    meet_client = GoogleMeetClient()
    logger.info("🔗 Meet client initialized")
except Exception as e:
    logger.warning(f"⚠️  Failed to initialize Meet client: {e}")
    meet_client = _PlaceholderClient()

# Some tests expect strava_client to be None initially (placeholder behavior)
strava_client = None

# NEW: Clean Architecture - Modern Command Processor
try:
    # Don't get MCP processor from registry during init - let command processor get it dynamically
    command_processor = ModernCommandProcessor(
        calendar_client=calendar_client,
        meet_client=meet_client, 
        sms_client=surge_client,
        mcp_processor=None  # Will be fetched dynamically from registry
    )
    logger.info("🤖 Modern Command Processor ready - Clean Architecture with Strategy/Command patterns and MCP integration")
except Exception as e:
    logger.warning(f"⚠️  Failed to initialize ModernCommandProcessor: {e}. Falling back to basic processor.")
    # Fallback to a simple processor
    class FallbackCommandProcessor:
        async def process_command(self, *args, **kwargs):
            return "Service temporarily unavailable. Please try again later."
        async def process_command_with_llm(self, *args, **kwargs):
            return "Service temporarily unavailable. Please try again later."
    
    command_processor = FallbackCommandProcessor()
