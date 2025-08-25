"""
Unit tests for SMS webhook processing and conversation context.
"""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from app.routers.webhook import (
    _process_sms_command, 
    _handle_new_user,
    _get_or_create_conversation,
    _update_conversation_context,
    _normalize_phone,
    _extract_name_from_message
)
from database.models import TeamMember, Conversation
from tests.conftest import create_sms_payload


class TestPhoneNormalization:
    """Test phone number normalization functionality."""
    
    def test_normalize_us_phone_with_country_code(self):
        """Test normalizing US phone with country code."""
        assert _normalize_phone("+15551234567") == "+15551234567"
        assert _normalize_phone("15551234567") == "+15551234567"
    
    def test_normalize_us_phone_without_country_code(self):
        """Test normalizing US phone without country code."""
        assert _normalize_phone("5551234567") == "+15551234567"
        assert _normalize_phone("(555) 123-4567") == "+15551234567"
        assert _normalize_phone("555-123-4567") == "+15551234567"
        assert _normalize_phone("555.123.4567") == "+15551234567"
    
    def test_normalize_international_phone(self):
        """Test normalizing international phone numbers."""
        assert _normalize_phone("+447911123456") == "+447911123456"
        assert _normalize_phone("447911123456") == "+447911123456"
    
    def test_normalize_phone_with_special_characters(self):
        """Test normalizing phone with various special characters."""
        assert _normalize_phone("(555) 123-4567 ext. 123") == "+15551234567123"
        assert _normalize_phone("+1 (555) 123-4567") == "+15551234567"


class TestNameExtraction:
    """Test name extraction from messages."""
    
    def test_extract_name_patterns(self):
        """Test various name extraction patterns."""
        assert _extract_name_from_message("My name is John Doe") == "John Doe"
        assert _extract_name_from_message("I'm Jane Smith") == "Jane Smith"
        assert _extract_name_from_message("I am Bob Johnson") == "Bob Johnson"
        assert _extract_name_from_message("Call me Mike") == "Mike"
    
    def test_extract_name_case_insensitive(self):
        """Test case insensitive name extraction."""
        assert _extract_name_from_message("MY NAME IS JOHN DOE") == "John Doe"
        assert _extract_name_from_message("my name is jane smith") == "Jane Smith"
    
    def test_extract_name_filters_common_words(self):
        """Test that common words are filtered from names."""
        # Should filter out common words
        result = _extract_name_from_message("My name is John and I am here")
        assert "and" not in result
        assert "I" not in result
    
    def test_extract_name_no_match(self):
        """Test when no name pattern is found."""
        assert _extract_name_from_message("Hello there") is None
        assert _extract_name_from_message("Schedule a meeting") is None


class TestConversationManagement:
    """Test conversation creation and context management."""
    
    def test_get_or_create_conversation_new(self, test_db_session):
        """Test creating a new conversation."""
        phone_number = "+15551234567"
        
        # Should not exist initially
        existing = test_db_session.query(Conversation).filter(
            Conversation.phone_number == phone_number
        ).first()
        assert existing is None
        
        # Create conversation
        conversation = _get_or_create_conversation(phone_number, test_db_session)
        
        assert conversation is not None
        assert conversation.phone_number == phone_number
        assert conversation.context == {}
        assert conversation.last_activity is not None
    
    def test_get_or_create_conversation_existing(self, test_db_session, sample_conversation):
        """Test getting an existing conversation."""
        phone_number = sample_conversation.phone_number
        
        # Get existing conversation
        conversation = _get_or_create_conversation(phone_number, test_db_session)
        
        assert conversation.id == sample_conversation.id
        assert conversation.phone_number == phone_number
    
    def test_update_conversation_context_new_message(self, test_db_session):
        """Test updating conversation context with new message."""
        conversation = Conversation(
            phone_number="+15551234567",
            context={}
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Update with first message
        _update_conversation_context(conversation, "Hello", test_db_session)
        
        assert "recent_messages" in conversation.context
        assert len(conversation.context["recent_messages"]) == 1
        assert conversation.context["recent_messages"][0]["message"] == "Hello"
    
    def test_update_conversation_context_multiple_messages(self, test_db_session):
        """Test conversation context with multiple messages."""
        conversation = Conversation(
            phone_number="+15551234567",
            context={
                "recent_messages": [
                    {"message": "First message", "timestamp": "2024-01-01T10:00:00"}
                ]
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Add second message
        _update_conversation_context(conversation, "Second message", test_db_session)
        
        assert len(conversation.context["recent_messages"]) == 2
        assert conversation.context["recent_messages"][1]["message"] == "Second message"
    
    def test_update_conversation_context_limit_messages(self, test_db_session):
        """Test that conversation context limits recent messages."""
        conversation = Conversation(
            phone_number="+15551234567",
            context={
                "recent_messages": [
                    {"message": f"Message {i}", "timestamp": f"2024-01-01T10:0{i}:00"}
                    for i in range(5)  # Already at limit
                ]
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Add one more message
        _update_conversation_context(conversation, "Sixth message", test_db_session)
        
        # Should still be 5 messages (oldest removed)
        assert len(conversation.context["recent_messages"]) == 5
        assert conversation.context["recent_messages"][-1]["message"] == "Sixth message"
        assert "Message 0" not in str(conversation.context["recent_messages"])


class TestNewUserHandling:
    """Test new user registration and handling."""
    
    @pytest.mark.asyncio
    async def test_handle_new_user_with_names(self, test_db_session):
        """Test handling new user with first and last name."""
        response = await _handle_new_user(
            "+15551234567", 
            "Hello", 
            "John", 
            "Doe", 
            test_db_session
        )
        
        assert "Welcome John Doe!" in response
        
        # Check user was created
        member = test_db_session.query(TeamMember).filter(
            TeamMember.phone == "+15551234567"
        ).first()
        assert member is not None
        assert member.name == "John Doe"
    
    @pytest.mark.asyncio
    async def test_handle_new_user_with_name_in_message(self, test_db_session):
        """Test handling new user with name in message."""
        response = await _handle_new_user(
            "+15551234567",
            "My name is Alice Johnson",
            "",
            "",
            test_db_session
        )
        
        assert "Welcome Alice Johnson!" in response
        
        # Check user was created
        member = test_db_session.query(TeamMember).filter(
            TeamMember.phone == "+15551234567"
        ).first()
        assert member is not None
        assert member.name == "Alice Johnson"
    
    @pytest.mark.asyncio
    async def test_handle_new_user_no_name_info(self, test_db_session):
        """Test handling new user without name information."""
        response = await _handle_new_user(
            "+15551234567",
            "Hello there",
            "",
            "",
            test_db_session
        )
        
        assert "Welcome! Reply with your name" in response
        
        # Check no user was created yet
        member = test_db_session.query(TeamMember).filter(
            TeamMember.phone == "+15551234567"
        ).first()
        assert member is None
    
    @pytest.mark.asyncio
    async def test_handle_new_user_creates_team_if_none_exists(self, test_db_session):
        """Test that new user creates team if none exists."""
        # Ensure no teams exist
        from database.models import Team
        existing_teams = test_db_session.query(Team).count()
        assert existing_teams == 0
        
        response = await _handle_new_user(
            "+15551234567",
            "My name is John Doe",
            "",
            "",
            test_db_session
        )
        
        # Check team was created
        teams = test_db_session.query(Team).all()
        assert len(teams) == 1
        assert teams[0].name == "Family"
        
        # Check user is admin (first user)
        member = test_db_session.query(TeamMember).filter(
            TeamMember.phone == "+15551234567"
        ).first()
        assert member.is_admin is True


class TestSMSCommandProcessing:
    """Test SMS command processing with context preservation."""
    
    @pytest.mark.asyncio
    async def test_process_sms_command_existing_user(self, test_db_session, sample_team_member, sample_conversation, mock_llm_processor):
        """Test processing SMS command for existing user."""
        with patch('app.services.command_processor', mock_llm_processor):
            response = await _process_sms_command(
                sample_team_member.phone,
                "Schedule a meeting tomorrow",
                "John",
                "Doe",
                test_db_session
            )
        
        # Should process with LLM
        assert len(mock_llm_processor.processed_commands) == 1
        command = mock_llm_processor.processed_commands[0]
        assert command["message_text"] == "Schedule a meeting tomorrow"
        assert command["team_member_id"] == sample_team_member.id
    
    @pytest.mark.asyncio
    async def test_process_sms_command_new_user(self, test_db_session):
        """Test processing SMS command for new user."""
        response = await _process_sms_command(
            "+15559999999",  # New phone number
            "Hello",
            "Jane",
            "Smith",
            test_db_session
        )
        
        # Should handle new user registration
        assert "Welcome Jane Smith!" in response
    
    @pytest.mark.asyncio
    async def test_process_sms_command_updates_conversation(self, test_db_session, sample_team_member, mock_llm_processor):
        """Test that processing SMS updates conversation context."""
        with patch('app.services.command_processor', mock_llm_processor):
            # First message
            await _process_sms_command(
                sample_team_member.phone,
                "First message",
                "John",
                "Doe",
                test_db_session
            )
            
            # Second message
            await _process_sms_command(
                sample_team_member.phone,
                "Second message",
                "John",
                "Doe",
                test_db_session
            )
        
        # Check conversation was updated
        conversation = test_db_session.query(Conversation).filter(
            Conversation.phone_number == sample_team_member.phone
        ).first()
        
        assert conversation is not None
        assert len(conversation.context["recent_messages"]) == 2
        assert conversation.context["recent_messages"][0]["message"] == "First message"
        assert conversation.context["recent_messages"][1]["message"] == "Second message"


class TestContextPreservation:
    """Test conversation context preservation across messages."""
    
    @pytest.mark.asyncio
    async def test_context_carries_between_messages(self, test_db_session, sample_team_member, mock_llm_processor):
        """Test that context is preserved between sequential messages."""
        with patch('app.services.command_processor', mock_llm_processor):
            # First message - start conversation
            await _process_sms_command(
                sample_team_member.phone,
                "Can we schedule a meeting?",
                "John",
                "Doe",
                test_db_session
            )
            
            # Second message - follow up
            await _process_sms_command(
                sample_team_member.phone,
                "How about tomorrow at 2pm?",
                "John",
                "Doe",
                test_db_session
            )
            
            # Third message - confirmation
            await _process_sms_command(
                sample_team_member.phone,
                "Yes, that works",
                "John",
                "Doe",
                test_db_session
            )
        
        # Verify all commands were processed with context
        assert len(mock_llm_processor.processed_commands) == 3
        
        # Check that each command has conversation context
        for i, command in enumerate(mock_llm_processor.processed_commands):
            assert command["conversation_id"] is not None
            # All should have the same conversation ID
            if i > 0:
                assert command["conversation_id"] == mock_llm_processor.processed_commands[0]["conversation_id"]
    
    def test_conversation_context_structure(self, test_db_session, sample_conversation):
        """Test that conversation context has expected structure."""
        context = sample_conversation.context
        
        # Should have recent messages
        assert "recent_messages" in context
        assert isinstance(context["recent_messages"], list)
        assert len(context["recent_messages"]) == 2
        
        # Each message should have proper structure
        for message in context["recent_messages"]:
            assert "message" in message
            assert "timestamp" in message
            assert isinstance(message["message"], str)
            assert isinstance(message["timestamp"], str)
        
        # Should have additional context fields
        assert "last_intent" in context
        assert "pending_confirmation" in context
    
    def test_conversation_context_pending_confirmation(self, test_db_session, sample_conversation):
        """Test conversation context with pending confirmation."""
        context = sample_conversation.context
        pending = context["pending_confirmation"]
        
        assert pending["type"] == "meeting_time"
        assert "details" in pending
        assert pending["details"]["title"] == "Team Meeting"
        assert pending["details"]["proposed_time"] == "2024-01-15T14:00:00"
        assert pending["details"]["duration"] == 60