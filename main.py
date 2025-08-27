"""FastAPI application entrypoint (modular, minimal).

All endpoints live in app/routers; shared singletons in app/services.
Updated: 2024-12-26 - Anthropic SDK v0.64.0 with tool calling support
Fixed: f-string formatting error with JSON content - v4 (ACTUAL FIX)
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uuid
from contextlib import asynccontextmanager
import logging
import os

from database.connection import create_tables
from app.routers import all_routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("startup")

@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
    try:
        create_tables()
        logger.info("🚀 Smart Meeting Orchestrator started (lifespan init)")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization failed: {e}. App will continue without database.")
        logger.info("🚀 Smart Meeting Orchestrator started (lifespan init - limited mode)")
    yield
    logger.info("👋 Lifespan shutdown")

app = FastAPI(
    title="Smart Meeting Orchestrator",
    description="SMS-based meeting coordination via SMS + Calendar + LLM",
    version="1.0.0",
    lifespan=lifespan,
)

def _include_routers(app: FastAPI):
    for router in all_routers:
        app.include_router(router)
        app.include_router(router, prefix="/v1")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # pragma: no cover
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={
        "error": {"type": exc.__class__.__name__, "message": str(exc)},
        "request_id": getattr(request.state, "request_id", None)
    })

_include_routers(app)

# Initialize MCP tools with error handling
try:
    from mcp_integration.mcp_command_processor import MCPCommandProcessor
    from mcp_integration.registry import set_mcp_processor
    from app.services import surge_client, calendar_client, meet_client, strava_client
    
    logger.info(f"🔧 Initializing MCP processor with clients: surge={type(surge_client).__name__}, calendar={type(calendar_client).__name__}, meet={type(meet_client).__name__}")
    logger.info(f"🔧 Environment check - ANTHROPIC_API_KEY present: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
    
    mcp_processor = MCPCommandProcessor(
        sms_client=surge_client,
        calendar_client=calendar_client,
        meet_client=meet_client,
        strava_client=strava_client
    )
    
    logger.info(f"🔧 MCP processor created: {mcp_processor}, llm_enabled={getattr(mcp_processor, 'llm_enabled', 'unknown')}")
    
    set_mcp_processor(mcp_processor)
    logger.info("🔧 MCP tools initialized and registered")
except Exception as e:
    logger.error(f"❌ Failed to initialize MCP tools: {e}", exc_info=True)
    mcp_processor = None


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

