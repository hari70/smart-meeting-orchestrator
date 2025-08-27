import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from database.models import TeamMember, Meeting, Team
from utils.time import utc_now

logger = logging.getLogger(__name__)

class CommandProcessor:
    def __init__(self, sms_client, calendar_client, meet_client):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        
        # Command patterns
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
        """Process incoming SMS command"""
        try:
            message_lower = message_text.lower().strip()
            
            # Determine command type
            command_type = self.classify_command(message_lower)
            
            logger.info(f"Processing command: {command_type} from {team_member.name}")
            
            if command_type == "schedule_meeting":
                return await self.handle_schedule_meeting(message_text, team_member, db)
            elif command_type == "list_meetings":
                return await self.handle_list_meetings(team_member, db)
            elif command_type == "cancel_meeting":
                return await self.handle_cancel_meeting(message_text, team_member, db)
            elif command_type == "availability":
                return await self.handle_check_availability(team_member, db)
            else:
                return await self.handle_general_query(message_text, team_member, db)
                
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            return "Sorry, I encountered an error processing your request. Please try again."
    
    def classify_command(self, message: str) -> str:
        """Classify the type of command"""
        for command_type, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    return command_type
        return "general"
    
    async def handle_schedule_meeting(self, message: str, team_member: TeamMember, db: Session) -> str:
        """Handle meeting scheduling requests"""
        try:
            # Extract meeting details
            meeting_info = self.extract_meeting_info(message)
            
            if not meeting_info:
                return "I couldn't understand the meeting details. Try: 'Family meeting about vacation this weekend'"
            
            # Get team members
            team = db.query(Team).filter(Team.id == team_member.team_id).first()
            if not team:
                return "Couldn't identify your team. Please ensure you're registered correctly."
            team_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
            
            # Find available time slot
            available_time = await self.find_available_time(team_members, meeting_info.get("when"))
            
            if not available_time:
                return "I couldn't find a time when everyone is available. Please suggest specific times."
            
            # Create Google Meet link
            meet_link = await self.meet_client.create_meeting(meeting_info["title"])
            
            # Create calendar event
            calendar_event = await self.calendar_client.create_event(
                title=meeting_info["title"],
                start_time=available_time,
                duration_minutes=60,
                attendees=[getattr(member, 'google_calendar_id') for member in team_members if getattr(member, 'google_calendar_id', None)],
                meet_link=meet_link
            )
            
            # Save to database
            meeting = Meeting(
                team_id=team.id,
                title=meeting_info["title"],
                description=meeting_info.get("description", ""),
                scheduled_time=available_time,
                google_meet_link=meet_link,
                google_calendar_event_id=calendar_event.get("id") if calendar_event else None,
                created_by_phone=team_member.phone
            )
            
            db.add(meeting)
            db.commit()
            
            # Format response
            time_str = available_time.strftime("%A, %B %d at %I:%M %p")
            response = f"""
✅ Meeting scheduled!

📅 {meeting_info['title']}
🕐 {time_str}
👥 All {len(team_members)} family members invited
🔗 Join: {meet_link}

Calendar invites sent to everyone with Google Calendar!
            """.strip()
            
            return response
            
        except Exception as e:
            logger.error(f"Error scheduling meeting: {str(e)}")
            return "Sorry, I couldn't schedule the meeting. Please try again or contact support."
    
    async def handle_list_meetings(self, team_member: TeamMember, db: Session) -> str:
        """Handle requests to list upcoming meetings"""
        try:
            # Get upcoming meetings for the team
            upcoming_meetings = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > utc_now()
            ).order_by(Meeting.scheduled_time).limit(5).all()
            
            if not upcoming_meetings:
                return "No upcoming meetings scheduled. Would you like to schedule one?"
            
            response = "📅 Upcoming meetings:\n\n"
            
            for i, meeting in enumerate(upcoming_meetings, 1):
                time_str = meeting.scheduled_time.strftime("%a %m/%d at %I:%M %p")
                response += f"{i}. {meeting.title}\n   {time_str}\n"
                if getattr(meeting, 'google_meet_link', None) is not None:
                    response += f"   🔗 {meeting.google_meet_link}\n"
                response += "\n"
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error listing meetings: {str(e)}")
            return "Sorry, I couldn't retrieve your meetings. Please try again."
    
    async def handle_cancel_meeting(self, message: str, team_member: TeamMember, db: Session) -> str:
        """Handle meeting cancellation requests"""
        # For MVP, let's handle the most recent meeting
        try:
            latest_meeting = db.query(Meeting).filter(
                Meeting.team_id == team_member.team_id,
                Meeting.scheduled_time > utc_now()
            ).order_by(Meeting.scheduled_time).first()
            
            if not latest_meeting:
                return "No upcoming meetings to cancel."
            
            # Cancel in Google Calendar if we have event ID
            if getattr(latest_meeting, 'google_calendar_event_id', None) is not None:
                await self.calendar_client.delete_event(latest_meeting.google_calendar_event_id)
            
            # Remove from database
            db.delete(latest_meeting)
            db.commit()
            
            return f"✅ Cancelled: {latest_meeting.title}"
            
        except Exception as e:
            logger.error(f"Error cancelling meeting: {str(e)}")
            return "Sorry, I couldn't cancel the meeting. Please try again."
    
    async def handle_check_availability(self, team_member: TeamMember, db: Session) -> str:
        """Handle availability check requests"""
        # For MVP, return a simple message
        return "Let me check everyone's availability... (Feature coming soon! For now, just suggest specific times.)"
    
    async def handle_general_query(self, message: str, team_member: TeamMember, db: Session) -> str:
        """Handle general queries and help"""
        help_text = """
🤖 I can help you with:

📅 Schedule meetings:
• "Family meeting about vacation this weekend"
• "Schedule call with everyone next week"

📋 Check meetings:
• "What's our next meeting?"
• "Show my meetings"

❌ Cancel meetings:
• "Cancel today's meeting"

Need help? Just ask!
        """.strip()
        
        return help_text
    
    def extract_meeting_info(self, message: str) -> Optional[Dict]:
        """Extract meeting information from message"""
        try:
            message_lower = message.lower()
            
            # Extract topic/title
            title_patterns = [
                r"(?:meeting|call)\s+about\s+(.+?)(?:\s+(?:this|next|tomorrow|today))",
                r"(?:family|team)\s+(?:meeting|call)\s+(.+?)(?:\s+(?:this|next|tomorrow|today))",
                r"schedule\s+(?:meeting|call)\s+(.+?)(?:\s+(?:this|next|tomorrow|today))"
            ]
            
            title = None
            for pattern in title_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    title = match.group(1).strip().title()
                    break
            
            if not title:
                # Fallback - try to extract after "about"
                about_match = re.search(r"about\s+(.+)", message_lower)
                if about_match:
                    title = about_match.group(1).strip().title()
                else:
                    title = "Family Meeting"
            
            # Extract timing
            when = None
            time_indicators = ["weekend", "week", "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            for indicator in time_indicators:
                if indicator in message_lower:
                    when = indicator
                    break
            
            return {
                "title": title,
                "when": when,
                "description": f"Meeting scheduled via SMS: {message}"
            }
            
        except Exception as e:
            logger.error(f"Error extracting meeting info: {str(e)}")
            return None
    
    async def find_available_time(self, team_members: List[TeamMember], when_hint: Optional[str] = None) -> Optional[datetime]:
        """Find available time for team members (placeholder heuristic)."""
        now = utc_now()
        if when_hint == "today":
            target_date = now.date()
        elif when_hint == "tomorrow":
            target_date = (now + timedelta(days=1)).date()
        elif when_hint == "weekend":
            # Find next Saturday
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            target_date = (now + timedelta(days=days_until_saturday)).date()
        else:
            # Default to tomorrow evening
            target_date = (now + timedelta(days=1)).date()
        target_time = datetime.combine(target_date, datetime.min.time().replace(hour=19))
        return target_time
