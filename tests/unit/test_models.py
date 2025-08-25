"""
Unit tests for database models.
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError

from database.models import Team, TeamMember, Meeting, Conversation, GUID


class TestTeamModel:
    """Test Team model functionality."""
    
    def test_create_team(self, test_db_session):
        """Test creating a new team."""
        team = Team(name="Test Family")
        test_db_session.add(team)
        test_db_session.commit()
        
        assert team.id is not None
        assert isinstance(team.id, uuid.UUID)
        assert team.name == "Test Family"
        assert team.created_at is not None
        assert isinstance(team.created_at, datetime)
    
    def test_team_name_required(self, test_db_session):
        """Test that team name is required."""
        team = Team()  # No name provided
        test_db_session.add(team)
        
        with pytest.raises(IntegrityError):
            test_db_session.commit()
    
    def test_team_name_length_limit(self, test_db_session):
        """Test team name length constraints."""
        # Test maximum length (should work)
        long_name = "A" * 100
        team = Team(name=long_name)
        test_db_session.add(team)
        test_db_session.commit()
        
        assert team.name == long_name


class TestTeamMemberModel:
    """Test TeamMember model functionality."""
    
    def test_create_team_member(self, test_db_session, sample_team):
        """Test creating a new team member."""
        member = TeamMember(
            team_id=sample_team.id,
            name="Jane Doe",
            phone="+15559876543",
            email="jane@example.com",
            is_admin=False
        )
        test_db_session.add(member)
        test_db_session.commit()
        
        assert member.id is not None
        assert isinstance(member.id, uuid.UUID)
        assert member.team_id == sample_team.id
        assert member.name == "Jane Doe"
        assert member.phone == "+15559876543"
        assert member.email == "jane@example.com"
        assert member.is_admin is False
        assert member.created_at is not None
    
    def test_team_member_required_fields(self, test_db_session, sample_team):
        """Test that required fields are enforced."""
        # Missing name
        with pytest.raises(IntegrityError):
            member = TeamMember(team_id=sample_team.id, phone="+15551234567")
            test_db_session.add(member)
            test_db_session.commit()
        
        test_db_session.rollback()
        
        # Missing phone
        with pytest.raises(IntegrityError):
            member = TeamMember(team_id=sample_team.id, name="John Doe")
            test_db_session.add(member)
            test_db_session.commit()
    
    def test_team_member_defaults(self, test_db_session, sample_team):
        """Test default values for team member."""
        member = TeamMember(
            team_id=sample_team.id,
            name="Test User",
            phone="+15551234567"
        )
        test_db_session.add(member)
        test_db_session.commit()
        
        assert member.email is None
        assert member.google_calendar_id is None
        assert member.preferences == {}
        assert member.is_admin is False
    
    def test_team_member_preferences_json(self, test_db_session, sample_team):
        """Test JSON preferences field."""
        preferences = {
            "timezone": "America/New_York",
            "preferred_meeting_times": ["09:00", "14:00"],
            "notifications": {"sms": True, "email": False}
        }
        
        member = TeamMember(
            team_id=sample_team.id,
            name="Test User",
            phone="+15551234567",
            preferences=preferences
        )
        test_db_session.add(member)
        test_db_session.commit()
        test_db_session.refresh(member)
        
        assert member.preferences == preferences
        assert member.preferences["timezone"] == "America/New_York"
        assert len(member.preferences["preferred_meeting_times"]) == 2


class TestMeetingModel:
    """Test Meeting model functionality."""
    
    def test_create_meeting(self, test_db_session, sample_team):
        """Test creating a new meeting."""
        scheduled_time = datetime.now(timezone.utc) + timedelta(days=1)
        
        meeting = Meeting(
            team_id=sample_team.id,
            title="Team Standup",
            description="Daily standup meeting",
            scheduled_time=scheduled_time,
            duration_minutes=30,
            google_meet_link="https://meet.google.com/abc-defg-hij",
            created_by_phone="+15551234567"
        )
        test_db_session.add(meeting)
        test_db_session.commit()
        
        assert meeting.id is not None
        assert isinstance(meeting.id, uuid.UUID)
        assert meeting.team_id == sample_team.id
        assert meeting.title == "Team Standup"
        assert meeting.scheduled_time == scheduled_time
        assert meeting.duration_minutes == 30
        assert meeting.created_at is not None
    
    def test_meeting_required_fields(self, test_db_session, sample_team):
        """Test that required fields are enforced."""
        # Missing title
        with pytest.raises(IntegrityError):
            meeting = Meeting(
                team_id=sample_team.id,
                scheduled_time=datetime.now(timezone.utc) + timedelta(days=1)
            )
            test_db_session.add(meeting)
            test_db_session.commit()
    
    def test_meeting_defaults(self, test_db_session, sample_team):
        """Test default values for meeting."""
        meeting = Meeting(
            team_id=sample_team.id,
            title="Test Meeting"
        )
        test_db_session.add(meeting)
        test_db_session.commit()
        
        assert meeting.duration_minutes == 60  # Default duration
        assert meeting.agenda == []  # Default empty agenda
        assert meeting.description is None
        assert meeting.google_meet_link is None
    
    def test_meeting_agenda_json(self, test_db_session, sample_team):
        """Test JSON agenda field."""
        agenda = [
            {"topic": "Project Updates", "duration": 15},
            {"topic": "Q&A", "duration": 10},
            {"topic": "Next Steps", "duration": 5}
        ]
        
        meeting = Meeting(
            team_id=sample_team.id,
            title="Weekly Review",
            agenda=agenda
        )
        test_db_session.add(meeting)
        test_db_session.commit()
        test_db_session.refresh(meeting)
        
        assert meeting.agenda == agenda
        assert len(meeting.agenda) == 3
        assert meeting.agenda[0]["topic"] == "Project Updates"


class TestConversationModel:
    """Test Conversation model functionality."""
    
    def test_create_conversation(self, test_db_session, sample_team):
        """Test creating a new conversation."""
        context = {
            "recent_messages": [
                {"message": "Hello", "timestamp": "2024-01-01T10:00:00"},
                {"message": "How are you?", "timestamp": "2024-01-01T10:01:00"}
            ],
            "last_intent": "greeting"
        }
        
        conversation = Conversation(
            phone_number="+15551234567",
            team_id=sample_team.id,
            context=context
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        assert conversation.id is not None
        assert isinstance(conversation.id, uuid.UUID)
        assert conversation.phone_number == "+15551234567"
        assert conversation.team_id == sample_team.id
        assert conversation.context == context
        assert conversation.last_activity is not None
    
    def test_conversation_required_fields(self, test_db_session):
        """Test that required fields are enforced."""
        # Missing phone_number
        with pytest.raises(IntegrityError):
            conversation = Conversation(context={})
            test_db_session.add(conversation)
            test_db_session.commit()
    
    def test_conversation_defaults(self, test_db_session):
        """Test default values for conversation."""
        conversation = Conversation(phone_number="+15551234567")
        test_db_session.add(conversation)
        test_db_session.commit()
        
        assert conversation.context == {}
        assert conversation.team_id is None
        assert conversation.last_activity is not None
    
    def test_conversation_context_updates(self, test_db_session):
        """Test updating conversation context."""
        conversation = Conversation(
            phone_number="+15551234567",
            context={"messages": []}
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Update context
        new_context = {
            "messages": ["Hello", "How are you?"],
            "intent": "greeting"
        }
        conversation.context = new_context
        test_db_session.commit()
        test_db_session.refresh(conversation)
        
        assert conversation.context == new_context
        assert len(conversation.context["messages"]) == 2


class TestGUIDType:
    """Test GUID type functionality."""
    
    def test_guid_generation(self, test_db_session):
        """Test that GUIDs are properly generated."""
        team1 = Team(name="Team 1")
        team2 = Team(name="Team 2")
        
        test_db_session.add_all([team1, team2])
        test_db_session.commit()
        
        # Should have different UUIDs
        assert team1.id != team2.id
        assert isinstance(team1.id, uuid.UUID)
        assert isinstance(team2.id, uuid.UUID)
    
    def test_guid_string_conversion(self, test_db_session):
        """Test GUID string conversion."""
        team = Team(name="Test Team")
        test_db_session.add(team)
        test_db_session.commit()
        
        # Should be able to convert to string and back
        team_id_str = str(team.id)
        assert len(team_id_str) == 36  # Standard UUID string length
        
        # Should be able to find by string ID
        found_team = test_db_session.query(Team).filter(
            Team.id == team_id_str
        ).first()
        assert found_team is not None
        assert found_team.id == team.id


class TestModelRelationships:
    """Test relationships between models."""
    
    def test_team_member_relationship(self, test_db_session, sample_team, sample_team_member):
        """Test team-member relationship."""
        # Access team from member
        assert sample_team_member.team_id == sample_team.id
        
        # Query members of a team
        members = test_db_session.query(TeamMember).filter(
            TeamMember.team_id == sample_team.id
        ).all()
        assert len(members) == 1
        assert members[0].id == sample_team_member.id
    
    def test_meeting_team_relationship(self, test_db_session, sample_team, sample_meeting):
        """Test meeting-team relationship."""
        assert sample_meeting.team_id == sample_team.id
        
        # Query meetings for a team
        meetings = test_db_session.query(Meeting).filter(
            Meeting.team_id == sample_team.id
        ).all()
        assert len(meetings) == 1
        assert meetings[0].id == sample_meeting.id
    
    def test_conversation_team_relationship(self, test_db_session, sample_team, sample_conversation):
        """Test conversation-team relationship."""
        assert sample_conversation.team_id == sample_team.id
        
        # Query conversations for a team
        conversations = test_db_session.query(Conversation).filter(
            Conversation.team_id == sample_team.id
        ).all()
        assert len(conversations) == 1
        assert conversations[0].id == sample_conversation.id