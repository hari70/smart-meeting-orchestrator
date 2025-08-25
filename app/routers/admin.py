from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app import services

from database.connection import get_db
from database.models import Team, TeamMember
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

def require_admin_key(x_api_key: str = Header(None, alias="X-API-Key")) -> bool:
    # Fetch fresh settings each call (lru cached but reflects env before process start; acceptable for tests when env set early)
    s = get_settings()
    key = s.admin_api_key
    if not key and s.environment not in ("production", "staging"):
        return True
    if not key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if not x_api_key or x_api_key != key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


def _normalize_phone(phone: str) -> str:
    import re
    cleaned = re.sub(r'[^\d+]', '', phone)
    if not cleaned.startswith('+'):
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+1' + cleaned
        else:
            cleaned = '+' + cleaned
    return cleaned


@router.post("/add-family-member")
async def add_family_member_simple(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        if not name or not phone:
            return JSONResponse(status_code=400, content={"error": "name and phone are required"})
        normalized_phone = _normalize_phone(phone)
        team = db.query(Team).filter(Team.name == "Family").first()
        if not team:
            team = Team(name="Family")
            db.add(team)
            db.commit()
            db.refresh(team)
        existing = db.query(TeamMember).filter(TeamMember.phone == normalized_phone).first()
        if existing:
            return JSONResponse(status_code=400, content={"error": f"{existing.name} with phone {normalized_phone} already exists"})
        member = TeamMember(team_id=team.id, name=name, phone=normalized_phone, email=email, is_admin=data.get("is_admin", False))
        db.add(member)
        db.commit()
        db.refresh(member)
        return {"success": True, "member": {"id": str(member.id), "name": member.name, "phone": member.phone, "team": team.name}}
    except Exception as e:
        logger.error(f"Error adding family member: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/family-members")
async def list_family_members(db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.name == "Family").first()
    if not team:
        return JSONResponse(status_code=404, content={"error": "No Family team found"})
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    return {
        "team": team.name,
        "members": [
            {"id": str(m.id), "name": m.name, "phone": m.phone, "email": m.email, "is_admin": m.is_admin}
            for m in members
        ]
    }


# ---------------------- Calendar Utility Endpoints ----------------------

@router.post("/calendar/test-event")
async def create_test_calendar_event(request: Request):
    """Create a sample (or real) Google Calendar event to verify integration.

    Request JSON fields (all optional except title):
      - title: str (default: "Test Event")
      - hours_from_now: int (default: 2) OR start_time_iso: explicit ISO8601
      - duration_minutes: int (default: 60)
      - attendees: list[str] (emails)
      - meet_link: optional custom meet link (if omitted, Google Meet conference requested)
    """
    data = await request.json()
    title = data.get("title", "Test Event")
    duration = int(data.get("duration_minutes", 60))
    attendees = data.get("attendees") or []
    meet_link = data.get("meet_link")

    # Determine start time
    if data.get("start_time_iso"):
        try:
            start_time = datetime.fromisoformat(data["start_time_iso"].replace("Z", "+00:00"))
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid start_time_iso"})
    else:
        hours_from_now = int(data.get("hours_from_now", 2))
        start_time = datetime.utcnow() + timedelta(hours=hours_from_now)

    result = await services.calendar_client.create_event(
        title=title,
        start_time=start_time,
        duration_minutes=duration,
        attendees=attendees,
        meet_link=meet_link,
    )

    if not result:
        return JSONResponse(status_code=500, content={"error": "Event creation failed", "calendar_enabled": services.calendar_client.enabled})

    return {
        "created": True,
        "mode": result.get("source"),
        "event": result,
        "calendar_enabled": services.calendar_client.enabled,
    }


@router.get("/calendar/events")
async def list_calendar_events(limit: int = 5):
    events = await services.calendar_client.list_events(limit=limit)
    return {"count": len(events), "events": events, "calendar_enabled": services.calendar_client.enabled}


@router.post("/calendar/check-conflicts")
async def check_conflicts(request: Request):
    data = await request.json()
    duration = int(data.get("duration_minutes", 60))
    attendees = data.get("attendees") or []
    if data.get("start_time_iso"):
        try:
            start_time = datetime.fromisoformat(data["start_time_iso"].replace("Z", "+00:00"))
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid start_time_iso"})
    else:
        hours_from_now = int(data.get("hours_from_now", 2))
        start_time = datetime.utcnow() + timedelta(hours=hours_from_now)
    conflicts = await services.calendar_client.check_conflicts(start_time=start_time, duration_minutes=duration, attendees=attendees)
    return {"start_time": start_time.isoformat(), **conflicts, "calendar_enabled": services.calendar_client.enabled}
