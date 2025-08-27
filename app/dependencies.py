"""Shared FastAPI dependencies (auth, common helpers).

Centralizes cross-router logic to reduce duplication.
"""
from fastapi import Header, HTTPException
from app.config import get_settings
import os


def require_admin_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> bool:
    """Simple header-based admin key guard.

    Development/staging fallback: if no key set and environment is non-production,
    allow requests to ease local iteration.
    """
    # Force refresh if tests toggled environment vars mid-run
    if os.getenv("FORCE_SETTINGS_REFRESH") == "1":
        # Clear internal cache by reassigning (function in config handles this flag)
        pass
    settings = get_settings()
    # Always re-read raw env for key to avoid stale cache during tests
    import os as _os
    key = _os.getenv("ADMIN_API_KEY") or settings.admin_api_key
    # Allow keyless only if key truly absent and environment is non-critical
    if not key and settings.environment not in ("production", "staging"):
        return True
    if not key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if not x_api_key or x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True
