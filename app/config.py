"""Configuration module centralizing environment access.

Step 1 refactor: introduce a Settings object instead of ad-hoc os.getenv calls.
Lightweight (no external dependency) to avoid adding packages yet.
"""
from functools import lru_cache
import os
from typing import Optional


class Settings:
    # Core
    environment: str = os.getenv("ENVIRONMENT", "development")
    port: int = int(os.getenv("PORT", "8000"))

    # Database
    database_url: Optional[str] = os.getenv("DATABASE_URL")

    # Surge SMS
    surge_api_key: Optional[str] = os.getenv("SURGE_SMS_API_KEY")
    surge_account_id: Optional[str] = os.getenv("SURGE_ACCOUNT_ID")

    # LLM / Anthropic
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # Google Calendar (direct)
    google_access_token: Optional[str] = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")
    google_refresh_token: Optional[str] = os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")
    google_client_id: Optional[str] = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
    google_client_secret: Optional[str] = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
    google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    # Feature flags
    enable_mcp_calendar: bool = os.getenv("ENABLE_MCP_CALENDAR", "false").lower() == "true"
    use_real_mcp_calendar: bool = os.getenv("USE_REAL_MCP_CALENDAR", "false").lower() == "true"
    use_direct_google_calendar: bool = os.getenv("USE_DIRECT_GOOGLE_CALENDAR", "true").lower() == "true"

    # Debug / Admin protection (future)
    admin_api_key: Optional[str] = os.getenv("ADMIN_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
