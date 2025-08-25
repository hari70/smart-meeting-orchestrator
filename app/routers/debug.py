from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import os

from app.config import get_settings
from app import services
from database.connection import get_db
from database.models import Team, TeamMember

settings = get_settings()

def require_admin_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    s = get_settings()
    key = s.admin_api_key
    if not key and s.environment not in ("production", "staging"):
        return True
    if not key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if not x_api_key or x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

router = APIRouter(prefix="/debug", tags=["debug"], dependencies=[Depends(require_admin_key)])
logger = logging.getLogger(__name__)


@router.get("/config")
async def debug_config():
    return {
        "surge_api_key_present": bool(settings.surge_api_key),
        "surge_account_id_present": bool(settings.surge_account_id),
        "database_url_present": bool(settings.database_url),
        "environment": settings.environment,
        "port": settings.port
    }


@router.post("/simulate-sms")
async def simulate_sms(request: Request, db: Session = Depends(get_db)):
    from app.routers.webhook import _normalize_phone, _get_team_member_by_phone, _get_or_create_conversation
    data = await request.json()
    phone = data.get("phone", "+1234567890")
    message = data.get("message", "Schedule family dinner tomorrow at 7pm")
    norm = _normalize_phone(phone)
    member = _get_team_member_by_phone(norm, db)
    if not member:
        return {"error": "No team member found for this phone"}
    conv = _get_or_create_conversation(norm, db)
    response = await services.command_processor.process_command_with_llm(message_text=message, team_member=member, conversation=conv, db=db)
    return {"success": True, "response": response}


@router.get("/sms-flow-status")
async def debug_sms_flow_status(db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.name == "Family").first()
    if not team:
        return {"error": "No Family team"}
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    member_info = []
    emails = 0
    for m in members:
        email_val = getattr(m, "email", None)
        if email_val:
            emails += 1
        member_info.append({"name": m.name, "phone": m.phone, "has_email": bool(email_val)})
    return {
        "team": team.name,
        "members": member_info,
        "members_with_email": emails,
        "llm_enabled": getattr(services.command_processor, 'llm_enabled', False),
        "calendar_enabled": getattr(services.calendar_client, 'enabled', False)
    }


@router.get("/calendar-status")
async def calendar_status():
    """Return diagnostics to verify real vs mock Google Calendar mode."""
    c = services.calendar_client
    # Mask sensitive parts
    def mask(v, keep=6):
        if not v:
            return None
        return v[:keep] + "…" + v[-4:]
    return {
        "enabled": c.enabled,
        "calendar_id": getattr(c, "calendar_id", "primary"),
        "has_access_token": bool(c.access_token),
        "access_token_sample": mask(c.access_token, 12),
        "has_refresh_token": bool(getattr(c, "refresh_token", None)),
        "refresh_token_sample": mask(getattr(c, "refresh_token", None), 6),
        "client_id_ok": bool(getattr(c, "client_id", "").endswith(".apps.googleusercontent.com")),
        "client_id_sample": mask(getattr(c, "client_id", None), 10),
        "client_secret_present": bool(getattr(c, "client_secret", None)),
        "mode_hint": "real_google_api" if c.enabled else "mock",
        "how_to_get_real": "Set GOOGLE_CALENDAR_ACCESS_TOKEN or refresh trio then restart process",
    }
