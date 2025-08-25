"""
End-to-end tests for complete user journeys.
"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from tests.conftest import create_sms_payload


class TestCompleteUserJourneys:
    """Test complete user workflows from SMS to response."""
    
    @pytest.mark.asyncio
    async def test_complete_new_user_journey(self, test_client, test_db_session):
        """Test complete journey for a new user."""
        from database.models import TeamMember, Team, Conversation
        
        phone_number = "+15551234567"
        
        # Step 1: New user sends first message
        payload = create_sms_payload(
            phone_number=phone_number,
            message="My name is Sarah Johnson",
            first_name="Sarah",
            last_name="Johnson"
        )
        
        response = test_client.post("/webhook/sms", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        
        # Verify user was created
        member = test_db_session.query(TeamMember).filter(
            TeamMember.phone == phone_number
        ).first()
        assert member is not None
        assert member.name == "Sarah Johnson"
        assert member.is_admin is True  # First user becomes admin
        
        # Verify team was created
        team = test_db_session.query(Team).first()
        assert team is not None
        assert team.name == "Family"
        
        # Verify conversation was created
        conversation = test_db_session.query(Conversation).filter(
            Conversation.phone_number == phone_number
        ).first()
        assert conversation is not None
        assert len(conversation.context["recent_messages"]) == 1
    
    @pytest.mark.asyncio
    async def test_complete_meeting_scheduling_journey(self, test_client, test_db_session, sample_team_member):
        """Test complete meeting scheduling workflow with context preservation."""
        from database.models import Conversation, Meeting
        
        # Mock the LLM processor and external services
        mock_processor = AsyncMock()
        mock_calendar_client = AsyncMock()
        mock_meet_client = AsyncMock()
        
        # Configure mocks
        mock_calendar_client.check_conflicts.return_value = {"has_conflicts": False}
        mock_calendar_client.create_event.return_value = {
            "id": "calendar_event_123",
            "success": True,
            "start_time": "2024-01-16T14:00:00Z"
        }
        mock_meet_client.create_meeting.return_value = "https://meet.google.com/abc-defg-hij"
        
        # Mock LLM responses for each step
        llm_responses = [
            "What time would work for the family meeting?",
            "How about tomorrow at 2pm - should I schedule that?",
            "✅ Family meeting scheduled for tomorrow at 2pm! Meet link: https://meet.google.com/abc-defg-hij"
        ]
        
        call_count = 0
        async def mock_llm_process(**kwargs):
            nonlocal call_count
            response = llm_responses[call_count]
            call_count += 1
            return response
        
        mock_processor.process_command_with_llm = mock_llm_process
        
        with patch('app.services.command_processor', mock_processor), \
             patch('app.services.calendar_client', mock_calendar_client), \
             patch('app.services.meet_client', mock_meet_client):
            
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Step 1: Initial meeting request
            payload1 = {**base_payload, "data": {**base_payload["data"], "body": "Can we schedule a family meeting?"}}
            response1 = test_client.post("/webhook/sms", json=payload1)
            assert response1.status_code == 200
            
            # Step 2: Specify time
            payload2 = {**base_payload, "data": {**base_payload["data"], "body": "How about tomorrow at 2pm?"}}
            response2 = test_client.post("/webhook/sms", json=payload2)
            assert response2.status_code == 200
            
            # Step 3: Confirm
            payload3 = {**base_payload, "data": {**base_payload["data"], "body": "Yes, that sounds perfect"}}
            response3 = test_client.post("/webhook/sms", json=payload3)
            assert response3.status_code == 200
            
            # Verify conversation context was maintained
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert conversation is not None
            assert len(conversation.context["recent_messages"]) == 3
            assert conversation.context["recent_messages"][0]["message"] == "Can we schedule a family meeting?"
            assert conversation.context["recent_messages"][2]["message"] == "Yes, that sounds perfect"
            
            # Verify all LLM calls were made with proper context
            assert mock_processor.process_command_with_llm.call_count == 3
    
    @pytest.mark.asyncio
    async def test_multi_step_confirmation_journey(self, test_client, test_db_session, sample_team_member):
        """Test journey with multiple confirmation steps."""
        from database.models import Conversation
        
        mock_processor = AsyncMock()
        
        # Responses that require confirmation
        confirmation_responses = [
            "I found a time conflict at 2pm. How about 3pm instead?",
            "Perfect! Should I invite the whole family to this meeting?",
            "✅ Meeting scheduled for tomorrow at 3pm with the whole family!"
        ]
        
        call_count = 0
        async def mock_confirmation_process(**kwargs):
            nonlocal call_count
            response = confirmation_responses[call_count]
            call_count += 1
            return response
        
        mock_processor.process_command_with_llm = mock_confirmation_process
        
        with patch('app.services.command_processor', mock_processor):
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Step 1: Initial request
            payload1 = {**base_payload, "data": {**base_payload["data"], "body": "Schedule meeting tomorrow at 2pm"}}
            response1 = test_client.post("/webhook/sms", json=payload1)
            assert response1.status_code == 200
            
            # Step 2: Respond to time conflict
            payload2 = {**base_payload, "data": {**base_payload["data"], "body": "Yes, 3pm works better"}}
            response2 = test_client.post("/webhook/sms", json=payload2)
            assert response2.status_code == 200
            
            # Step 3: Confirm family invitation
            payload3 = {**base_payload, "data": {**base_payload["data"], "body": "Yes, invite everyone"}}
            response3 = test_client.post("/webhook/sms", json=payload3)
            assert response3.status_code == 200
            
            # Verify each step maintained context
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            # Should have rich context with confirmations
            assert len(conversation.context["recent_messages"]) == 3
            assert "last_intent" in conversation.context
    
    @pytest.mark.asyncio
    async def test_context_preservation_across_time_gaps(self, test_client, test_db_session, sample_team_member):
        """Test context preservation with time gaps between messages."""
        from database.models import Conversation
        
        mock_processor = AsyncMock()
        
        # Responses that show context awareness
        time_aware_responses = [
            "I can help schedule that meeting. When would you like it?",
            "Great! Continuing with the meeting we discussed earlier - tomorrow at 2pm works!",
            "✅ Meeting confirmed for tomorrow at 2pm as we planned!"
        ]
        
        call_count = 0
        async def mock_time_aware_process(**kwargs):
            nonlocal call_count
            # Verify conversation context is passed
            conversation = kwargs.get('conversation')
            assert conversation is not None
            
            response = time_aware_responses[call_count]
            call_count += 1
            return response
        
        mock_processor.process_command_with_llm = mock_time_aware_process
        
        with patch('app.services.command_processor', mock_processor):
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Step 1: Start conversation
            payload1 = {**base_payload, "data": {**base_payload["data"], "body": "I need to schedule a family meeting"}}
            response1 = test_client.post("/webhook/sms", json=payload1)
            assert response1.status_code == 200
            
            # Simulate time gap by manually updating conversation timestamp
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            conversation.last_activity = datetime.utcnow() - timedelta(hours=1)
            test_db_session.commit()
            
            # Step 2: Continue conversation after gap
            payload2 = {**base_payload, "data": {**base_payload["data"], "body": "How about tomorrow at 2pm?"}}
            response2 = test_client.post("/webhook/sms", json=payload2)
            assert response2.status_code == 200
            
            # Step 3: Final confirmation
            payload3 = {**base_payload, "data": {**base_payload["data"], "body": "Yes, that's perfect"}}
            response3 = test_client.post("/webhook/sms", json=payload3)
            assert response3.status_code == 200
            
            # Verify context was preserved despite time gap
            final_conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert len(final_conversation.context["recent_messages"]) == 3
            assert final_conversation.context["message_count"] == 3
    
    @pytest.mark.asyncio
    async def test_error_recovery_journey(self, test_client, test_db_session, sample_team_member):
        """Test user journey with error recovery."""
        from database.models import Conversation
        
        mock_processor = AsyncMock()
        
        # Simulate error then recovery
        error_then_recovery_responses = [
            "I had trouble processing that request. Could you try again?",
            "Now I understand! Let me schedule that meeting for you.",
            "✅ Meeting successfully scheduled!"
        ]
        
        call_count = 0
        async def mock_error_recovery(**kwargs):
            nonlocal call_count
            response = error_then_recovery_responses[call_count]
            call_count += 1
            return response
        
        mock_processor.process_command_with_llm = mock_error_recovery
        
        with patch('app.services.command_processor', mock_processor):
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Step 1: Ambiguous request
            payload1 = {**base_payload, "data": {**base_payload["data"], "body": "meeting thing"}}
            response1 = test_client.post("/webhook/sms", json=payload1)
            assert response1.status_code == 200
            
            # Step 2: Clarified request
            payload2 = {**base_payload, "data": {**base_payload["data"], "body": "Schedule family meeting tomorrow 2pm"}}
            response2 = test_client.post("/webhook/sms", json=payload2)
            assert response2.status_code == 200
            
            # Step 3: Final confirmation
            payload3 = {**base_payload, "data": {**base_payload["data"], "body": "Yes please"}}
            response3 = test_client.post("/webhook/sms", json=payload3)
            assert response3.status_code == 200
            
            # Verify error and recovery were tracked in context
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert len(conversation.context["recent_messages"]) == 3
            # All interactions should be preserved
            assert conversation.context["recent_messages"][0]["message"] == "meeting thing"
            assert conversation.context["recent_messages"][1]["message"] == "Schedule family meeting tomorrow 2pm"


class TestConcurrentUserJourneys:
    """Test multiple users interacting simultaneously."""
    
    @pytest.mark.asyncio
    async def test_concurrent_users_isolated_contexts(self, test_client, test_db_session, sample_team):
        """Test that concurrent users have isolated conversation contexts."""
        from database.models import TeamMember, Conversation
        
        # Create multiple users
        users = []
        for i in range(3):
            user = TeamMember(
                team_id=sample_team.id,
                name=f"User {i+1}",
                phone=f"+155512345{i+10}"
            )
            test_db_session.add(user)
            users.append(user)
        test_db_session.commit()
        
        mock_processor = AsyncMock()
        mock_processor.process_command_with_llm.return_value = "Processed!"
        
        with patch('app.services.command_processor', mock_processor):
            # Each user sends messages simultaneously
            for i, user in enumerate(users):
                for j in range(3):  # 3 messages per user
                    payload = create_sms_payload(
                        phone_number=user.phone,
                        message=f"User {i+1} message {j+1}",
                        first_name=f"User",
                        last_name=f"{i+1}"
                    )
                    
                    response = test_client.post("/webhook/sms", json=payload)
                    assert response.status_code == 200
            
            # Verify each user has isolated context
            for i, user in enumerate(users):
                conversation = test_db_session.query(Conversation).filter(
                    Conversation.phone_number == user.phone
                ).first()
                
                assert conversation is not None
                assert len(conversation.context["recent_messages"]) == 3
                
                # Verify messages belong to correct user
                for j, message in enumerate(conversation.context["recent_messages"]):
                    expected_message = f"User {i+1} message {j+1}"
                    assert message["message"] == expected_message