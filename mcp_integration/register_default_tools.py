from __future__ import annotations
from datetime import datetime
from mcp_integration.base import ToolDefinition, tool_registry
from app import services


def register_calendar_tools():
    calendar = services.calendar_client

    async def create_calendar_event(**kwargs):
        summary = kwargs.get("summary")
        start_time = kwargs.get("start_time")
        duration_minutes = kwargs.get("duration_minutes", 60)
        attendees = kwargs.get("attendees") or []
        if not summary or not start_time:
            return {"error": "missing_required_fields"}
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        res = await calendar.create_event(title=summary, start_time=start, duration_minutes=duration_minutes, attendees=attendees, meet_link=None)
        return res or {"error": "creation_failed"}

    async def list_upcoming_events(**kwargs):
        limit = kwargs.get("limit", 5)
        events = await calendar.list_events(limit=limit)
        return {"events": events}

    async def check_time_conflicts(**kwargs):
        start_time = kwargs.get("start_time")
        duration_minutes = kwargs.get("duration_minutes", 60)
        if not start_time:
            return {"error": "missing_start_time"}
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        return await calendar.check_conflicts(start_time=start, duration_minutes=duration_minutes)

    tool_registry.register(ToolDefinition(
        name="calendar.create_event",
        description="Create a calendar event (generic abstraction)",
        schema={"type": "object", "properties": {"summary": {"type": "string"}, "start_time": {"type": "string"}, "duration_minutes": {"type": "integer"}, "attendees": {"type": "array", "items": {"type": "string"}}, "description": {"type": "string"}}, "required": ["summary", "start_time"]},
        executor=create_calendar_event,
    ))
    tool_registry.register(ToolDefinition(
        name="calendar.list_events",
        description="List upcoming events",
        schema={"type": "object", "properties": {"limit": {"type": "integer"}}},
        executor=list_upcoming_events,
    ))
    tool_registry.register(ToolDefinition(
        name="calendar.check_conflicts",
        description="Check conflicts for a proposed time window",
        schema={"type": "object", "properties": {"start_time": {"type": "string"}, "duration_minutes": {"type": "integer"}}, "required": ["start_time"]},
        executor=check_time_conflicts,
    ))


def initialize_default_tools():
    try:
        register_calendar_tools()
    except Exception:  # pragma: no cover
        import logging
        logging.getLogger(__name__).exception("Failed registering default tools")
