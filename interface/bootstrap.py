from __future__ import annotations
import logging
from adapters.calendar.mcp_calendar_provider import MCPCalendarProvider
from sms_coordinator.surge_client import SurgeSMSClient
from app.config import get_settings

logger = logging.getLogger(__name__)

class Bootstrap:
    def __init__(self):
        self.settings = get_settings()
        self.calendar_provider = None
        self.sms_client = None

    def init(self):
        self._calendar()
        self._sms()
        return self

    def _calendar(self):
        self.calendar_provider = MCPCalendarProvider()
        logger.info("calendar_provider initialized (MCP only)")
        return self.calendar_provider

    def _sms(self):
        self.sms_client = SurgeSMSClient(
            api_key=self.settings.surge_api_key or "", 
            account_id=self.settings.surge_account_id or ""
        )
        return self.sms_client

def bootstrap():
    return Bootstrap().init()
