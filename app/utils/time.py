"""Time/date related helpers."""
from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import HTTPException


def compute_start_time(hours_from_now: int | None, start_time_iso: str | None) -> datetime:
    """Compute a timezone-naive UTC start time.

    Accept either hours_from_now or explicit ISO8601 string. Raises HTTPException on invalid input.
    """
    if start_time_iso:
        try:
            # Accept trailing Z
            return datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid start_time_iso")
    # fallback
    hrs = hours_from_now if hours_from_now is not None else 2
    return datetime.utcnow() + timedelta(hours=hrs)
