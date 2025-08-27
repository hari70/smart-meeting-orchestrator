"""Pydantic models for request/response bodies.

Adding explicit schemas improves validation, documentation and reduces
ad-hoc dict access complexity inside route handlers.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class CalendarTestEventRequest(BaseModel):
    title: str = Field(default="Test Event")
    hours_from_now: Optional[int] = Field(default=2, ge=0)
    start_time_iso: Optional[str] = Field(default=None, description="Explicit ISO8601 start time (exclusive with hours_from_now)")
    duration_minutes: int = Field(default=60, gt=0, le=24*60)
    attendees: List[str] = Field(default_factory=list)
    meet_link: Optional[str] = None

    @field_validator("start_time_iso")
    @classmethod
    def validate_mutual_exclusion(cls, v, info):
        data = info.data
        if v and data.get("hours_from_now") is not None and data.get("hours_from_now") != 2:
            raise ValueError("Provide either start_time_iso or hours_from_now, not both")
        return v


class CalendarConflictCheckRequest(BaseModel):
    hours_from_now: Optional[int] = Field(default=2, ge=0)
    start_time_iso: Optional[str] = None
    duration_minutes: int = Field(default=60, gt=0, le=24*60)
    attendees: List[str] = Field(default_factory=list)


class SimpleSuccessResponse(BaseModel):
    success: bool = True
