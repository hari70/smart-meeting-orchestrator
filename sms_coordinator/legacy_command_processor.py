"""Legacy CommandProcessor extracted from supporting_modules.

Purpose: isolate legacy regex-based command handling so we can migrate
away from inline utcnow usage and indentation issues in the monolithic
supporting_modules file. This module is a drop-in substitute for
`sms_coordinator.command_processor.CommandProcessor` where needed.
"""
from __future__ import annotations
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from database.models import TeamMember, Meeting, Team
from utils.time import utc_now

logger = logging.getLogger(__name__)

class LegacyCommandProcessor:
    def __init__(self, sms_client, calendar_client, meet_client):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        self.patterns = {
            "schedule_meeting": [
                r"(?:family|team)?\s*(?:meeting|call)\s+about\s+(.+?)\s+(?:this|next)?\s*(week|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)",
                r"schedule\s+(?:call|meeting)\s+with\s+(.+?)\s+(?:this|next)?\s*(week|weekend|today|tomorrow)",
                r"(?:family|team)\s+(?:call|meeting)\s+(.+)"
            ],
            "list_meetings": [
                r"(?:what|when)(?:'s|'re)?\s+(?:our|my|the)?\s*(?:next|upcoming)?\s*meetings?",
                r"show\s+(?:my|our)?\s*meetings",
                r"agenda"
            ],
            "cancel_meeting": [
                r"cancel\s+(?:today's|tomorrow's|the)?\s*(?:meeting|call)",
                r"(?:delete|remove)\s+meeting"
            ],
            "availability": [
                r"(?:when|what time)\s+(?:is|are)\s+(?:we|everyone)\s+(?:free|available)",
                r"find\s+time\s+for\s+(?:meeting|call)",
                r"availability"
            ]
        }

    async def process_command(self, message_text: str, team_member: TeamMember, conversation, db: Session) -> str:
        try:
            message_lower = message_text.lower().strip()
            command_type = self.classify_command(message_lower)
            logger.info(f"[LEGACY_CMD] {command_type} from {team_member.name}")
            handler_map = {
                "schedule_meeting": self.handle_schedule_meeting,
                "list_meetings": self.handle_list_meetings,
                "cancel_meeting": self.handle_cancel_meeting,
                "availability": self.handle_check_availability,
                "general": self.handle_general_query,
            }
            handler = handler_map.get(command_type, self.handle_general_query)
            return await handler(message_text, team_member, db) if command_type != "list_meetings" else await handler(team_member, db)  # type: ignore[arg-type]
        except Exception as e:  # pragma: no cover
            logger.error(f"Legacy command error: {e}")
            return "Sorry, I encountered an error processing your request. Please try again."

    def classify_command(self, message: str) -> str:
        for command_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return command_type
        return "general"

    async def handle_schedule_meeting(self, message: str, team_member: TeamMember, db: Session) -> str:
        try:
            meeting_info = self.extract_meeting_info(message)
            if not meeting_info:
                return "I couldn't understand the meeting details. Try: 'Family meeting about vacation this weekend'"
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all() if team else []
            available_time = await self.find_available_time(team_members, meeting_info.get("when"))
            if not available_time:
                return "I couldn't find a time when everyone is available. Please suggest specific times."
            meet_link = await self.meet_client.create_meeting(meeting_info["title"]) if self.meet_client else "(no link)"
            calendar_event = await self.calendar_client.create_event(
                title=meeting_info["title"],
                start_time=available_time,
                duration_minutes=60,
                attendees=[m.google_calendar_id for m in team_members if getattr(m, 'google_calendar_id', None)],
                meet_link=meet_link
            ) if self.calendar_client else None
            meeting = Meeting(
                team_id=team.id if team else None,
                title=meeting_info["title"],
                description=meeting_info.get("description", ""),
                scheduled_time=available_time,
                google_meet_link=meet_link,
                google_calendar_event_id=calendar_event.get("id") if calendar_event else None,
                created_by_phone=team_member.phone
            )
            db.add(meeting); db.commit()
            time_str = available_time.strftime("%A, %B %d at %I:%M %p")
            return (f"✅ Meeting scheduled!\n\n📅 {meeting_info['title']}\n🕐 {time_str}\n👥 Participants: {len(team_members)}\n🔗 {meet_link}").strip()
        except Exception as e:  # pragma: no cover
            logger.error(f"Legacy schedule error: {e}")
            return "Sorry, I couldn't schedule the meeting. Please try again or contact support."

    async def handle_list_meetings(self, team_member: TeamMember, db: Session) -> str:
        try:
            upcoming = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > utc_now()
            ).order_by(Meeting.scheduled_time).limit(5).all()
            if not upcoming:
                return "No upcoming meetings scheduled. Would you like to schedule one?"
            lines = ["📅 Upcoming meetings:\n"]
            for i, m in enumerate(upcoming, 1):
                t_str = m.scheduled_time.strftime("%a %m/%d at %I:%M %p")
                link = f"\n   🔗 {m.google_meet_link}" if getattr(m, 'google_meet_link', None) else ""
                lines.append(f"{i}. {m.title}\n   {t_str}{link}\n")
            return "".join(lines).strip()
        except Exception as e:  # pragma: no cover
            logger.error(f"Legacy list error: {e}")
            return "Sorry, I couldn't retrieve your meetings. Please try again."

    async def handle_cancel_meeting(self, message: str, team_member: TeamMember, db: Session) -> str:
        try:
            latest = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > utc_now()
            ).order_by(Meeting.scheduled_time).first()
            if not latest:
                return "No upcoming meetings to cancel."
            if getattr(latest, 'google_calendar_event_id', None) and self.calendar_client:
                await self.calendar_client.delete_event(latest.google_calendar_event_id)
            db.delete(latest); db.commit()
            return f"✅ Cancelled: {latest.title}"
        except Exception as e:  # pragma: no cover
            logger.error(f"Legacy cancel error: {e}")
            return "Sorry, I couldn't cancel the meeting. Please try again."

    async def handle_check_availability(self, team_member: TeamMember, db: Session) -> str:
        return "Availability feature coming soon. Please propose a specific time."

    async def handle_general_query(self, message: str, team_member: TeamMember, db: Session) -> str:
        return ("🤖 Commands: schedule meeting, list meetings, cancel meeting. "
                "Example: 'Family meeting about vacation this weekend'")

    def extract_meeting_info(self, message: str) -> Optional[Dict]:
        try:
            lower = message.lower()
            title_patterns = [
                r"(?:meeting|call)\s+about\s+(.+?)(?:\s+(?:this|next|tomorrow|today))",
                r"(?:family|team)\s+(?:meeting|call)\s+(.+?)(?:\s+(?:this|next|tomorrow|today))",
                r"schedule\s+(?:meeting|call)\s+(.+?)(?:\s+(?:this|next|tomorrow|today))"
            ]
            title = None
            for pattern in title_patterns:
                m = re.search(pattern, lower)
                if m:
                    title = m.group(1).strip().title(); break
            if not title:
                about = re.search(r"about\s+(.+)", lower)
                title = about.group(1).strip().title() if about else "Family Meeting"
            when = None
            for indicator in ["weekend","week","tomorrow","today","monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
                if indicator in lower:
                    when = indicator; break
            return {"title": title, "when": when, "description": f"Scheduled via SMS: {message}"}
        except Exception as e:  # pragma: no cover
            logger.error(f"Legacy extract error: {e}"); return None

    async def find_available_time(self, team_members: List[TeamMember], when_hint: Optional[str]) -> Optional[datetime]:
        now = utc_now()
        if when_hint == "today":
            target_date = now.date()
        elif when_hint == "tomorrow":
            target_date = (now + timedelta(days=1)).date()
        elif when_hint == "weekend":
            days_until_sat = (5 - now.weekday()) % 7 or 7
            target_date = (now + timedelta(days=days_until_sat)).date()
        else:
            target_date = (now + timedelta(days=1)).date()
        return datetime.combine(target_date, datetime.min.time().replace(hour=19))
