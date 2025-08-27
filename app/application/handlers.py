"""Application layer: Command handlers implementing business logic."""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import TeamMember, Meeting
from app.domain.commands import CommandHandler
from app.infrastructure.repositories import MeetingRepository, TeamRepository
from app.domain.events import MeetingScheduled, event_dispatcher
from utils.time import utc_now

logger = logging.getLogger(__name__)


class ScheduleMeetingHandler(CommandHandler):
    """Handler for scheduling meetings."""
    
    def __init__(self, meeting_repo: MeetingRepository, team_repo: TeamRepository, 
                 calendar_client, meet_client):
        self.meeting_repo = meeting_repo
        self.team_repo = team_repo
        self.calendar_client = calendar_client
        self.meet_client = meet_client
    
    async def handle(self, message: str, team_member: TeamMember, db: Session) -> str:
        try:
            meeting_info = self._extract_meeting_info(message)
            if not meeting_info:
                return "I couldn't understand the meeting details. Try: 'Family meeting about vacation this weekend'"
            
            team = self.team_repo.get_by_id(str(team_member.team_id))
            if not team:
                return "Couldn't identify your team. Please ensure you're registered correctly."
            
            team_members = self.team_repo.get_members(str(team.id))
            available_time = await self._find_available_time(team_members, meeting_info.get("when"))
            
            if not available_time:
                return "I couldn't find a time when everyone is available. Please suggest specific times."
            
            meet_link = await self.meet_client.create_meeting(meeting_info["title"]) if self.meet_client else "(no link)"
            
            calendar_event = await self.calendar_client.create_event(
                title=meeting_info["title"],
                start_time=available_time,
                duration_minutes=60,
                attendees=[getattr(member, 'google_calendar_id') for member in team_members if getattr(member, 'google_calendar_id', None)],
                meet_link=meet_link
            ) if self.calendar_client else None
            
            meeting = Meeting(
                team_id=team.id,
                title=meeting_info["title"],
                description=meeting_info.get("description", ""),
                scheduled_time=available_time,
                google_meet_link=meet_link,
                google_calendar_event_id=calendar_event.get("id") if calendar_event else None,
                created_by_phone=team_member.phone
            )
            
            self.meeting_repo.save(meeting)
            
            # Fire domain event
            await event_dispatcher.dispatch(MeetingScheduled(meeting))
            
            time_str = available_time.strftime("%A, %B %d at %I:%M %p")
            return f"✅ Meeting scheduled!\n\n📅 {meeting_info['title']}\n🕐 {time_str}\n👥 Participants: {len(team_members)}\n🔗 {meet_link}".strip()
            
        except Exception as e:
            logger.error(f"Error scheduling meeting: {str(e)}")
            return "Sorry, I couldn't schedule the meeting. Please try again or contact support."
    
    def _extract_meeting_info(self, message: str) -> Optional[Dict]:
        # Simplified extraction - can be enhanced
        return {"title": "Meeting", "when": "tomorrow", "description": f"Scheduled via SMS: {message}"}
    
    async def _find_available_time(self, team_members, when_hint: Optional[str] = None) -> Optional[datetime]:
        now = utc_now()
        if when_hint == "today":
            target_date = now.date()
        elif when_hint == "tomorrow":
            target_date = (now + timedelta(days=1)).date()
        else:
            target_date = (now + timedelta(days=1)).date()
        return datetime.combine(target_date, datetime.min.time().replace(hour=19))


class ListMeetingsHandler(CommandHandler):
    """Handler for listing meetings."""
    
    def __init__(self, meeting_repo: MeetingRepository):
        self.meeting_repo = meeting_repo
    
    async def handle(self, message: str, team_member: TeamMember, db: Session) -> str:
        try:
            upcoming = self.meeting_repo.get_upcoming(str(team_member.team_id), limit=5)
            if not upcoming:
                return "No upcoming meetings scheduled. Would you like to schedule one?"
            
            lines = ["📅 Upcoming meetings:\n"]
            for i, m in enumerate(upcoming, 1):
                t_str = m.scheduled_time.strftime("%a %m/%d at %I:%M %p")
                link = f"\n   🔗 {m.google_meet_link}" if getattr(m, 'google_meet_link', None) else ""
                lines.append(f"{i}. {m.title}\n   {t_str}{link}\n")
            return "".join(lines).strip()
            
        except Exception as e:
            logger.error(f"Error listing meetings: {str(e)}")
            return "Sorry, I couldn't retrieve your meetings. Please try again."


class CancelMeetingHandler(CommandHandler):
    """Handler for cancelling meetings."""
    
    def __init__(self, meeting_repo: MeetingRepository, calendar_client):
        self.meeting_repo = meeting_repo
        self.calendar_client = calendar_client
    
    async def handle(self, message: str, team_member: TeamMember, db: Session) -> str:
        try:
            latest = self.meeting_repo.get_latest(str(team_member.team_id))
            if not latest:
                return "No upcoming meetings to cancel."
            
            if getattr(latest, 'google_calendar_event_id', None) and self.calendar_client:
                await self.calendar_client.delete_event(latest.google_calendar_event_id)
            
            self.meeting_repo.delete(latest)
            return f"✅ Cancelled: {latest.title}"
            
        except Exception as e:
            logger.error(f"Error cancelling meeting: {str(e)}")
            return "Sorry, I couldn't cancel the meeting. Please try again."


class GeneralQueryHandler(CommandHandler):
    """Handler for general queries."""
    
    async def handle(self, message: str, team_member: TeamMember, db: Session) -> str:
        return ("🤖 Commands: schedule meeting, list meetings, cancel meeting. "
                "Example: 'Family meeting about vacation this weekend'")
