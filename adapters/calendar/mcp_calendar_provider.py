from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
from core.calendar_event import CalendarEvent

class MCPCalendarProvider:
    """Thin adapter converting RealMCPCalendarClient dict results into CalendarEvent objects."""

    def __init__(self):
        self._client = RealMCPCalendarClient()

    async def list_events(self, days_ahead: int = 7, limit: int = 10) -> List[CalendarEvent]:
        raw = await self._client.list_events(days_ahead=days_ahead, limit=limit)
        events: List[CalendarEvent] = []
        for e in raw:
            start_raw = e.get("start_time_iso") or e.get("start_time") or e.get("start")
            if not start_raw:
                continue
            try:
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_raw.replace('Z','+00:00'))
            except Exception:
                continue
            events.append(CalendarEvent(
                id=e.get("id",""),
                title=e.get("title") or e.get("summary") or "(untitled)",
                start=start_dt,
                end=None,
                meet_link=e.get("meet_link") or e.get("hangoutLink"),
                calendar_link=e.get("calendar_link") or e.get("htmlLink"),
                attendees=e.get("attendees", []),
                source=e.get("source","mcp")
            ))
        return events

    async def create_event(self, title: str, start: datetime, duration_minutes: int = 60, attendees: Optional[List[str]] = None) -> Optional[CalendarEvent]:
        result = await self._client.create_event(title, start, duration_minutes, attendees or [])
        if not result:
            return None
        start_dt = datetime.fromisoformat(result["start_time"]) if result.get("start_time") else start
        end_dt = None
        try:
            if result.get("end_time"):
                end_dt = datetime.fromisoformat(result["end_time"])
        except Exception:
            pass
        return CalendarEvent(
            id=result.get("id",""),
            title=result.get("title", title),
            start=start_dt,
            end=end_dt,
            meet_link=result.get("meet_link"),
            calendar_link=result.get("calendar_link"),
            attendees=result.get("attendees", attendees or []),
            source=result.get("source","mcp")
        )
