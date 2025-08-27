from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app import services
from app.dependencies import require_admin_key
from app.schemas import (
    CalendarTestEventRequest,
    CalendarConflictCheckRequest,
)
from app.utils.time import compute_start_time

from database.connection import get_db
from database.models import Team, TeamMember
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

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
async def create_test_calendar_event(payload: CalendarTestEventRequest):
    """Create a sample (or real) Google Calendar event to verify integration."""
    start_time = compute_start_time(payload.hours_from_now, payload.start_time_iso)
    result = await services.calendar_client.create_event(
        title=payload.title,
        start_time=start_time,
        duration_minutes=payload.duration_minutes,
        attendees=payload.attendees,
        meet_link=payload.meet_link,
    )
    if not result:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Event creation failed",
                "calendar_enabled": getattr(services.calendar_client, "enabled", False),
            },
        )
    return {
        "created": True,
        "mode": result.get("source"),
        "event": result,
        "calendar_enabled": getattr(services.calendar_client, "enabled", False),
    }


@router.get("/calendar/events")
async def list_calendar_events(limit: int = 5):
    events = await services.calendar_client.list_events(limit=limit)
    return {
        "count": len(events),
        "events": events,
        "calendar_enabled": getattr(services.calendar_client, "enabled", False),
    }


@router.post("/calendar/check-conflicts")
async def check_conflicts(payload: CalendarConflictCheckRequest):
    start_time = compute_start_time(payload.hours_from_now, payload.start_time_iso)
    conflicts = await services.calendar_client.check_conflicts(
        start_time=start_time,
        duration_minutes=payload.duration_minutes,
        attendees=payload.attendees,
    )
    return {
        "start_time": start_time.isoformat(),
        **conflicts,
        "calendar_enabled": getattr(services.calendar_client, "enabled", False),
    }
