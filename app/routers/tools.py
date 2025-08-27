from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import require_admin_key
from mcp_integration.base import tool_registry
from pydantic import BaseModel
from typing import Any, Dict
import os

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

# TEMPORARY: Public endpoint for debugging (remove after fixing)
@router.get("/debug-anthropic")
async def debug_anthropic():
    """PUBLIC DEBUG: Test Anthropic API key and client initialization"""
    try:
        import anthropic
        anthropic_available = True
        anthropic_version = anthropic.__version__
    except ImportError:
        anthropic_available = False
        anthropic_version = None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    api_key_present = bool(api_key)
    api_key_length = len(api_key) if api_key else 0
    api_key_prefix = api_key[:10] if api_key else None

    # Try to initialize client
    client_initialized = False
    client_error = None
    api_call_success = False
    api_call_error = None

    if anthropic_available and api_key_present:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client_initialized = True

            # Try a simple API call
            try:
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=50,
                    temperature=0.0,
                    system="You are a helpful assistant.",
                    messages=[{"role": "user", "content": "Say 'test'"}]
                )
                api_call_success = True
            except Exception as e:
                api_call_error = str(e)

        except Exception as e:
            client_error = str(e)

    return {
        "anthropic_available": anthropic_available,
        "anthropic_version": anthropic_version,
        "api_key_present": api_key_present,
        "api_key_length": api_key_length,
        "api_key_prefix": api_key_prefix,
        "client_initialized": client_initialized,
        "client_error": client_error,
        "api_call_success": api_call_success,
        "api_call_error": api_call_error
    }

@router.get("/anthropic-test")
async def test_anthropic():
    """Test Anthropic API key and client initialization"""
    try:
        import anthropic
        anthropic_available = True
        anthropic_version = anthropic.__version__
    except ImportError:
        anthropic_available = False
        anthropic_version = None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    api_key_present = bool(api_key)
    api_key_length = len(api_key) if api_key else 0
    api_key_prefix = api_key[:10] if api_key else None

    # Try to initialize client
    client_initialized = False
    client_error = None
    api_call_success = False
    api_call_error = None

    if anthropic_available and api_key_present:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client_initialized = True

            # Try a simple API call
            try:
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=50,
                    temperature=0.0,
                    system="You are a helpful assistant.",
                    messages=[{"role": "user", "content": "Say 'test'"}]
                )
                api_call_success = True
            except Exception as e:
                api_call_error = str(e)

        except Exception as e:
            client_error = str(e)

    return {
        "anthropic_available": anthropic_available,
        "anthropic_version": anthropic_version,
        "api_key_present": api_key_present,
        "api_key_length": api_key_length,
        "api_key_prefix": api_key_prefix,
        "client_initialized": client_initialized,
        "client_error": client_error,
        "api_call_success": api_call_success,
        "api_call_error": api_call_error
    }
