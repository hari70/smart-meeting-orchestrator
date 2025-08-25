from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Team, TeamMember, Meeting

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Smart Meeting Orchestrator", "status": "running", "version": "1.0.0"}


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/teams")
async def list_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [{"id": str(team.id), "name": team.name} for team in teams]


@router.get("/teams/{team_id}/members")
async def list_team_members(team_id: str, db: Session = Depends(get_db)):
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    return [
        {"id": str(m.id), "name": m.name, "phone": m.phone, "is_admin": m.is_admin}
        for m in members
    ]


@router.get("/meetings")
async def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(10).all()
    return [
        {
            "id": str(meeting.id),
            "title": meeting.title,
            "scheduled_time": meeting.scheduled_time.isoformat() if getattr(meeting, "scheduled_time", None) else None,
            "google_meet_link": meeting.google_meet_link
        }
        for meeting in meetings
    ]
