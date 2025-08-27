"""Configuration module centralizing environment access.

Step 1 refactor: introduce a Settings object instead of ad-hoc os.getenv calls.
Lightweight (no external dependency) to avoid adding packages yet.
"""
import os
from typing import Optional


class Settings:
    def __init__(self) -> None:
        # Core
        inferred_testing = (
            os.getenv("PYTEST_CURRENT_TEST")
            or os.getenv("PYTEST_RUNNING") == "1"
            or os.getenv("ENVIRONMENT") == "testing"
            or os.getenv("TESTING") == "1"
            or os.getenv("FORCE_TEST_ENV") == "1"
            or (
                (os.getenv("SURGE_SMS_API_KEY") == "test_key" or os.getenv("ANTHROPIC_API_KEY") == "test_anthropic_key")
                and os.getenv("DATABASE_URL", "").startswith("sqlite:///:memory:")
            )
        )
        self.environment: str = "testing" if inferred_testing else os.getenv("ENVIRONMENT", "development")
        self.port: int = int(os.getenv("PORT", "8000"))

        # Database
        self.database_url: Optional[str] = os.getenv("DATABASE_URL") or "sqlite:///./app.db"

        # Surge SMS
        self.surge_api_key: Optional[str] = os.getenv("SURGE_SMS_API_KEY") or os.getenv("SURGE_API_KEY") or os.getenv("SURGE_APIKEY")
        self.surge_account_id: Optional[str] = os.getenv("SURGE_ACCOUNT_ID") or os.getenv("SURGE_SMS_ACCOUNT_ID") or os.getenv("SURGE_ACCOUNT")

        # LLM / Anthropic
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        self.llm_enabled: bool = bool(self.anthropic_api_key)

        # Google Calendar (direct)
        self.google_access_token: Optional[str] = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
        self.google_refresh_token: Optional[str] = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")
        self.google_client_id: Optional[str] = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
        self.google_client_secret: Optional[str] = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        self.google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

        # Feature flags
        self.enable_mcp_calendar: bool = os.getenv("ENABLE_MCP_CALENDAR", "false").lower() == "true"
        self.use_real_mcp_calendar: bool = os.getenv("USE_REAL_MCP_CALENDAR", "false").lower() == "true"
        self.use_direct_google_calendar: bool = os.getenv("USE_DIRECT_GOOGLE_CALENDAR", "true").lower() == "true"

        # Debug / Admin protection (future)
        self.admin_api_key: Optional[str] = os.getenv("ADMIN_API_KEY")


_SETTINGS_CACHE: Optional[Settings] = None


def get_settings(refresh: bool = False) -> Settings:
    """Return a (possibly cached) Settings instance.

    Pass refresh=True (or set env FORCE_SETTINGS_REFRESH=1) in tests after
    modifying environment variables to force re-evaluation.
    """
    global _SETTINGS_CACHE
    import sys
    if refresh or os.getenv("FORCE_SETTINGS_REFRESH") == "1" or _SETTINGS_CACHE is None:
        _SETTINGS_CACHE = Settings()
    else:
        # Auto-refresh if test env indicators appear after initial cache
        if (
            (os.getenv("ENVIRONMENT") == "testing" or os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PYTEST_RUNNING") == "1")
            and _SETTINGS_CACHE.environment != "testing"
        ):
            _SETTINGS_CACHE = Settings()
    # If pytest modules loaded but env not set yet, force testing mode
    if _SETTINGS_CACHE.environment != 'testing':
        import sys
        if any(m.startswith('tests.') or m.startswith('test_') for m in sys.modules.keys()):
            _SETTINGS_CACHE.environment = 'testing'
    # Sync llm_enabled on existing coordinator if present
    if 'app.services' in sys.modules:
        try:
            from app import services  # type: ignore
            if hasattr(services, 'command_processor'):
                services.command_processor.llm_enabled = bool(_SETTINGS_CACHE.anthropic_api_key)
        except Exception:
            pass
    return _SETTINGS_CACHE
