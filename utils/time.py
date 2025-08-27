"""Time utilities: timezone-aware helpers replacing naive utcnow usage."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

__all__ = ["utc_now", "iso_utc"]

def utc_now() -> datetime:
    """Return an aware UTC datetime."""
    return datetime.now(timezone.utc)

def iso_utc(dt: Optional[datetime] = None) -> str:
    """Return ISO8601 string with Z suffix for given datetime (defaults to now)."""
    if dt is None:
        dt = utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
