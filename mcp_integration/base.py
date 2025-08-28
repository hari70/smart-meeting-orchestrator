from __future__ import annotations
from typing import Protocol, Any, Dict, List, Optional

class ToolExecutable(Protocol):
    async def __call__(self, **kwargs) -> Any: ...  # pragma: no cover

class ToolDefinition:
    def __init__(self, name: str, description: str, schema: Dict, executor: ToolExecutable):
        self.name = name
        self.description = description
        self.schema = schema
        self.executor = executor

    async def invoke(self, **kwargs):
        return await self.executor(**kwargs)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def list(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in self._tools.values()
        ]

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    async def call(self, name: str, **kwargs):
        import logging, time
        logger = logging.getLogger("tool.invoke")
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        start = time.time()
        try:
            result = await tool.invoke(**kwargs)
            logger.info("tool=%s status=success elapsed_ms=%.1f args_keys=%s", name, (time.time()-start)*1000, list(kwargs.keys()))
            return result
        except Exception:
            logger.exception("tool=%s status=error elapsed_ms=%.1f", name, (time.time()-start)*1000)
            raise

# Global singleton
tool_registry = ToolRegistry()

# MCP Tool Definitions for Google Calendar
def register_google_calendar_mcp_tools():
    """Register the 8 Google Calendar MCP tools that are available in Railway environment"""
    import os, logging
    logger = logging.getLogger(__name__)

    mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
    if not mcp_endpoint:
        # New directive: assume MCP is always intended; log warning but continue so code paths remain deterministic
        logger.warning("⚠️ RAILWAY_MCP_ENDPOINT not set at import; MCP tool executors will raise if invoked. Registration proceeds for deterministic MCP-only architecture.")

    async def create_gcal_event(**kwargs):
        """Create a Google Calendar event"""
        # This will call the actual MCP tool available in Railway
        import os
        import requests
        import json

        # Get Railway MCP endpoint from environment
        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        # Call the actual MCP tool
        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:create_gcal_event",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def list_gcal_events(**kwargs):
        """List Google Calendar events"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:list_gcal_events",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def update_gcal_event(**kwargs):
        """Update a Google Calendar event"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:update_gcal_event",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def delete_gcal_event(**kwargs):
        """Delete a Google Calendar event"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:delete_gcal_event",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def search_gcal_events(**kwargs):
        """Search Google Calendar events"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:search_gcal_events",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def get_gcal_event(**kwargs):
        """Get a specific Google Calendar event"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:get_gcal_event",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def create_gcal_calendar(**kwargs):
        """Create a Google Calendar"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:create_gcal_calendar",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    async def delete_gcal_calendar(**kwargs):
        """Delete a Google Calendar"""
        import os
        import requests
        import json

        mcp_endpoint = os.getenv("RAILWAY_MCP_ENDPOINT")
        if not mcp_endpoint:
            return {"error": "MCP endpoint missing", "detail": "Set RAILWAY_MCP_ENDPOINT to enable calendar tools"}

        response = requests.post(
            f"{mcp_endpoint}/tools/invoke",
            json={
                "tool": "google-calendar:delete_gcal_calendar",
                "arguments": kwargs
            },
            headers={"Authorization": f"Bearer {os.getenv('RAILWAY_API_TOKEN', '')}"}
        )

        if response.status_code == 200:
            return response.json()["result"]
        else:
            raise Exception(f"MCP tool call failed: {response.text}")

    # Register all 8 Google Calendar MCP tools
    tool_registry.register(ToolDefinition(
        name="google-calendar:create_gcal_event",
        description="Create a new Google Calendar event with title, time, attendees, and description",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "summary": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "Start time in ISO format"},
                "end": {"type": "string", "description": "End time in ISO format"},
                "time_zone": {"type": "string", "description": "Time zone (e.g., 'America/New_York')"},
                "attendees": {"type": "array", "items": {"type": "object", "properties": {"email": {"type": "string"}}}},
                "description": {"type": "string", "description": "Event description"},
                "location": {"type": "string", "description": "Event location"}
            },
            "required": ["summary", "start", "end"]
        },
        executor=create_gcal_event
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:list_gcal_events",
        description="List Google Calendar events within a date range",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "time_min": {"type": "string", "description": "Start time in ISO format"},
                "time_max": {"type": "string", "description": "End time in ISO format"},
                "max_results": {"type": "integer", "description": "Maximum number of events to return"},
                "single_events": {"type": "boolean", "description": "Whether to expand recurring events"}
            }
        },
        executor=list_gcal_events
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:update_gcal_event",
        description="Update an existing Google Calendar event",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "event_id": {"type": "string", "description": "ID of the event to update"},
                "summary": {"type": "string", "description": "New event title"},
                "start": {"type": "string", "description": "New start time in ISO format"},
                "end": {"type": "string", "description": "New end time in ISO format"},
                "description": {"type": "string", "description": "New event description"}
            },
            "required": ["event_id"]
        },
        executor=update_gcal_event
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:delete_gcal_event",
        description="Delete a Google Calendar event",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "event_id": {"type": "string", "description": "ID of the event to delete"}
            },
            "required": ["event_id"]
        },
        executor=delete_gcal_event
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:search_gcal_events",
        description="Search Google Calendar events by text query",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "query": {"type": "string", "description": "Search query text"},
                "time_min": {"type": "string", "description": "Start time in ISO format"},
                "time_max": {"type": "string", "description": "End time in ISO format"}
            },
            "required": ["query"]
        },
        executor=search_gcal_events
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:get_gcal_event",
        description="Get details of a specific Google Calendar event",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "Calendar ID (usually 'primary')"},
                "event_id": {"type": "string", "description": "ID of the event to retrieve"}
            },
            "required": ["event_id"]
        },
        executor=get_gcal_event
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:create_gcal_calendar",
        description="Create a new Google Calendar",
        schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Calendar name"},
                "description": {"type": "string", "description": "Calendar description"}
            },
            "required": ["summary"]
        },
        executor=create_gcal_calendar
    ))

    tool_registry.register(ToolDefinition(
        name="google-calendar:delete_gcal_calendar",
        description="Delete a Google Calendar",
        schema={
            "type": "object",
            "properties": {
                "calendar_id": {"type": "string", "description": "ID of the calendar to delete"}
            },
            "required": ["calendar_id"]
        },
        executor=delete_gcal_calendar
    ))

    import logging
    logger = logging.getLogger(__name__)
    logger.info("✅ Registered 8 Google Calendar MCP tools in registry")
