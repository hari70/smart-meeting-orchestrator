"""Health and readiness endpoints for deployment platforms (Railway)."""
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()

@router.get("/health")
async def health():  # pragma: no cover
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

@router.get("/readiness")
async def readiness():  # pragma: no cover
    # Future: add DB ping, external service checks
    return {"ready": True, "ts": datetime.now(timezone.utc).isoformat()}
