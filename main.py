"""FastAPI application entrypoint (modular, minimal).

All endpoints live in app/routers; shared singletons in app/services.
Updated: 2024-12-26 - Anthropic SDK v0.64.0 with tool calling support
Fixed: f-string formatting error with JSON content - v4 (ACTUAL FIX)
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from database.connection import create_tables
from app.routers import all_routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("startup")

@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
    create_tables()
    logger.info("🚀 Smart Meeting Orchestrator started (lifespan init)")
    yield
    logger.info("👋 Lifespan shutdown")

app = FastAPI(
    title="Smart Meeting Orchestrator",
    description="SMS-based meeting coordination via SMS + Calendar + LLM",
    version="1.0.0",
    lifespan=lifespan,
)

for router in all_routers:
    app.include_router(router)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

