from __future__ import annotations
from typing import Optional
from mcp_integration.mcp_command_processor import MCPCommandProcessor as _LegacyMCP


class CommandProcessor:
    """Facade wrapping legacy MCPCommandProcessor to allow future incremental refactor.

    Exposes only the methods the interface layer should call.
    """

    def __init__(self, sms_client, calendar_client, meet_client, strava_client=None):
        self._inner = _LegacyMCP(
            sms_client=sms_client,
            calendar_client=calendar_client,
            meet_client=meet_client,
            strava_client=strava_client,
        )

    @property
    def llm_enabled(self) -> bool:
        return getattr(self._inner, 'llm_enabled', False)

    async def process_sms(self, text: str, team_member, conversation, db_session):
        # For now route to LLM path directly; later we can add rule-based fallback
        return await self._inner.process_command_with_llm(text, team_member, conversation, db_session)

    async def process_command_with_llm(self, text: str, team_member, conversation, db_session):
        """Facade compatibility so other components (ModernCommandProcessor) can retrieve an MCP processor from registry."""
        import os, logging
        logger = logging.getLogger(__name__)
        api_present = bool(os.getenv("ANTHROPIC_API_KEY"))
        if not self.llm_enabled:
            logger.warning(
                "LLM disabled in facade: api_present=%s anthropic_imported=%s", api_present, hasattr(self._inner, 'claude_client')
            )
        return await self._inner.process_command_with_llm(text, team_member, conversation, db_session)
