from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass(slots=True)
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: Optional[datetime] = None
    meet_link: Optional[str] = None
    calendar_link: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    source: str = "mcp"

    @property
    def duration_minutes(self) -> Optional[int]:
        if self.end:
            return int((self.end - self.start).total_seconds() // 60)
        return None
