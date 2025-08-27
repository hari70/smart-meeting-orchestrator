import logging, json
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ToolsMixin:
    async def _execute_mcp_tool(self, tool_name: str, tool_input: Dict, team_member, db, message_text: str) -> Dict:  # type: ignore[override]
        handler = getattr(self, f"_tool_{tool_name.replace('.', '_')}", None)
        if handler:
            return await handler(tool_input, team_member, db, message_text)
        return {"error": f"Unknown tool: {tool_name}"}
