"""Health and readiness endpoints for deployment platforms (Railway)."""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database.connection import get_db

router = APIRouter()

@router.get("/health")
async def health():
    """Simple liveness probe - always returns ok if service is running."""
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

@router.get("/readiness")
async def readiness(db: Session = Depends(get_db)):
    """Readiness probe - checks database connectivity."""
    try:
        # Simple database connectivity check
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"ready": True, "ts": datetime.now(timezone.utc).isoformat(), "database": "connected"}
    except Exception as e:
        return {"ready": False, "ts": datetime.now(timezone.utc).isoformat(), "database": f"error: {str(e)}"}
