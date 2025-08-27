"""
Pytest configuration and shared fixtures for Smart Meeting Orchestrator tests.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database.models import Base, Team, TeamMember, Meeting, Conversation
from database.connection import get_db
from main import app


@pytest.fixture(scope="session")
def test_db_engine():
    """Create a test database engine using SQLite in memory."""
    # Use in-memory SQLite for fast tests
    # Use file-based SQLite to allow multiple connections (TestClient + direct sessions)
    tmp_path = os.path.join(tempfile.gettempdir(), "smo_test_db.sqlite")
    engine = create_engine(
        f"sqlite:///{tmp_path}",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Create a fresh database session for each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=test_db_engine
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up tables between tests using session
        with test_db_engine.connect() as connection:
            with connection.begin():
                for table in reversed(Base.metadata.sorted_tables):
                    connection.execute(table.delete())


@pytest.fixture(scope="function")
def test_client(test_db_session):
    """Create a test client with overridden database dependency."""
    
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def sample_team(test_db_session):
    """Create a sample team for testing."""
    team = Team(name="Test Family")
    test_db_session.add(team)
    test_db_session.commit()
    test_db_session.refresh(team)
    return team


@pytest.fixture
def sample_team_member(test_db_session, sample_team):
    """Create a sample team member for testing."""
    member = TeamMember(
        team_id=sample_team.id,
        name="John Doe",
        phone="+15551234567",
        email="john@example.com",
        is_admin=True
    )
    test_db_session.add(member)
    test_db_session.commit()
    test_db_session.refresh(member)
    return member


@pytest.fixture
def sample_conversation(test_db_session, sample_team):
    """Create a sample conversation with context for testing."""
    now = datetime.now(timezone.utc)
    conversation = Conversation(
        phone_number="+15551234567",
        team_id=sample_team.id,
        context={
            "recent_messages": [
                {
                    "message": "Can we schedule a meeting?",
                    "timestamp": (now - timedelta(minutes=5)).isoformat()
                },
                {
                    "message": "How about tomorrow at 2pm?",
                    "timestamp": (now - timedelta(minutes=3)).isoformat()
                }
            ],
            "last_intent": "schedule_meeting",
            "pending_confirmation": {
                "type": "meeting_time",
                "details": {
                    "title": "Team Meeting",
                    "proposed_time": "2024-01-15T14:00:00",
                    "duration": 60
                }
            }
        },
        last_activity=now
    )
    test_db_session.add(conversation)
    test_db_session.commit()
    test_db_session.refresh(conversation)
    return conversation


@pytest.fixture
def sample_meeting(test_db_session, sample_team, sample_team_member):
    """Create a sample meeting for testing."""
    meeting = Meeting(
        team_id=sample_team.id,
        title="Test Meeting",
        description="A test meeting",
        scheduled_time=datetime.now(timezone.utc) + timedelta(days=1),
        duration_minutes=60,
        google_meet_link="https://meet.google.com/test-link",
        created_by_phone=sample_team_member.phone
    )
    test_db_session.add(meeting)
    test_db_session.commit()
    test_db_session.refresh(meeting)
    return meeting


@pytest.fixture
def sms_webhook_payload():
    """Standard SMS webhook payload for testing."""
    return {
        "type": "message.received",
        "data": {
            "conversation": {
                "contact": {
                    "phone_number": "+15551234567",
                    "first_name": "John",
                    "last_name": "Doe"
                }
            },
            "body": "Test message"
        }
    }


@pytest.fixture
def mock_surge_client():
    """Mock Surge SMS client for testing."""
    class MockSurgeClient:
        def __init__(self):
            self.sent_messages = []
        
        async def send_message(self, phone_number, message, first_name="", last_name=""):
            self.sent_messages.append({
                "phone_number": phone_number,
                "message": message,
                "first_name": first_name,
                "last_name": last_name
            })
            return {"success": True}
    
    return MockSurgeClient()


@pytest.fixture
def mock_llm_processor():
    """Mock LLM processor for testing."""
    class MockLLMProcessor:
        def __init__(self):
            self.processed_commands = []
        
        async def process_command_with_llm(self, message_text, team_member, conversation, db):
            self.processed_commands.append({
                "message_text": message_text,
                "team_member_id": team_member.id,
                "conversation_id": conversation.id if conversation else None
            })
            
            # Return different responses based on message content
            if "schedule" in message_text.lower():
                return "✅ Meeting scheduled for tomorrow at 2pm!"
            elif "list" in message_text.lower() or "meetings" in message_text.lower():
                return "📅 You have 2 upcoming meetings this week."
            elif "cancel" in message_text.lower():
                return "✅ Meeting cancelled successfully."
            else:
                return "I can help you schedule meetings, list upcoming events, or cancel meetings."
    
    return MockLLMProcessor()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    test_env_vars = {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite:///:memory:",
        "SURGE_SMS_API_KEY": "test_key",
        "SURGE_ACCOUNT_ID": "test_account",
        "ANTHROPIC_API_KEY": "test_anthropic_key"
    }
    
    # Store original values
    original_values = {}
    for key, value in test_env_vars.items():
        original_values[key] = os.getenv(key)
        os.environ[key] = value
    
    yield
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# Utility functions for tests
def assert_sms_response_format(response_text):
    """Assert that SMS response follows expected format."""
    assert isinstance(response_text, str)
    assert len(response_text) > 0
    assert len(response_text) <= 1600  # SMS length limit


def create_sms_payload(phone_number="+15551234567", message="Test", first_name="John", last_name="Doe"):
    """Helper to create SMS webhook payload."""
    return {
        "type": "message.received",
        "data": {
            "conversation": {
                "contact": {
                    "phone_number": phone_number,
                    "first_name": first_name,
                    "last_name": last_name
                }
            },
            "body": message
        }
    }