from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import require_admin_key
from mcp_integration.base import tool_registry
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(require_admin_key)])

class ToolInvokeRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}

@router.get("/list")
async def list_tools():
    return {"tools": tool_registry.list()}


@router.get("/discovery")
async def discovery():
    """Provide tool metadata for LLM prompt injection / agent planning."""
    tools = tool_registry.list()
    return {
        "count": len(tools),
        "tools": tools,
        "prompt_snippet": "Available tools: " + ", ".join(t["name"] for t in tools)
    }

@router.post("/invoke")
async def invoke_tool(payload: ToolInvokeRequest):
    try:
        result = await tool_registry.call(payload.tool, **payload.arguments)
        return {"tool": payload.tool, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Invocation failed: {e}")
