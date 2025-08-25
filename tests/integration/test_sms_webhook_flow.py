"""
Integration tests for SMS webhook flow with context preservation.
"""
import pytest
from unittest.mock import patch, AsyncMock
import json
from datetime import datetime, timedelta

from tests.conftest import create_sms_payload


class TestSMSWebhookIntegration:
    """Test complete SMS webhook integration flow."""
    
    @pytest.mark.asyncio
    async def test_complete_new_user_onboarding_flow(self, test_client):
        """Test complete new user onboarding via SMS."""
        # First message - user introduction
        payload = create_sms_payload(
            phone_number="+15551111111",
            message="My name is Alice Johnson",
            first_name="Alice",
            last_name="Johnson"
        )
        
        response = test_client.post("/webhook/sms", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        
        # Verify user was created and welcomed
        # (In a real test, we'd verify the SMS was sent)
    
    @pytest.mark.asyncio
    async def test_complete_meeting_scheduling_flow(self, test_client, sample_team_member):
        """Test complete meeting scheduling flow with context preservation."""
        base_payload = create_sms_payload(
            phone_number=sample_team_member.phone,
            message="",
            first_name="John",
            last_name="Doe"
        )
        
        # Message 1: Initial scheduling request
        payload1 = {**base_payload, "data": {**base_payload["data"], "body": "Can we schedule a family meeting?"}}
        response1 = test_client.post("/webhook/sms", json=payload1)
        assert response1.status_code == 200
        
        # Message 2: Specify time
        payload2 = {**base_payload, "data": {**base_payload["data"], "body": "How about tomorrow at 2pm?"}}
        response2 = test_client.post("/webhook/sms", json=payload2)
        assert response2.status_code == 200
        
        # Message 3: Confirmation
        payload3 = {**base_payload, "data": {**base_payload["data"], "body": "Yes, that sounds good"}}
        response3 = test_client.post("/webhook/sms", json=payload3)
        assert response3.status_code == 200
    
    @pytest.mark.asyncio 
    async def test_context_preservation_across_messages(self, test_client, test_db_session, sample_team_member):
        """Test that conversation context is preserved across multiple SMS exchanges."""
        from database.models import Conversation
        
        base_payload = create_sms_payload(
            phone_number=sample_team_member.phone,
            message="",
            first_name="John", 
            last_name="Doe"
        )
        
        messages = [
            "I need to schedule something",
            "It's for the whole family", 
            "How about this weekend?",
            "Saturday would be perfect",
            "Let's do 2pm"
        ]
        
        for i, message in enumerate(messages):
            payload = {**base_payload, "data": {**base_payload["data"], "body": message}}
            response = test_client.post("/webhook/sms", json=payload)
            assert response.status_code == 200
            
            # Check conversation context after each message
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert conversation is not None
            assert len(conversation.context["recent_messages"]) == min(i + 1, 5)  # Limited to 5
            assert conversation.context["recent_messages"][-1]["message"] == message
    
    def test_invalid_webhook_payload(self, test_client):
        """Test handling of invalid webhook payloads."""
        # Missing required fields
        invalid_payload = {"type": "message.received"}
        
        response = test_client.post("/webhook/sms", json=invalid_payload)
        assert response.status_code == 400
        assert "Invalid SMS payload" in response.json()["error"]
    
    def test_non_message_webhook_events(self, test_client):
        """Test handling of non-message webhook events."""
        payload = {
            "type": "delivery.status",  # Different event type
            "data": {"status": "delivered"}
        }
        
        response = test_client.post("/webhook/sms", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
    
    @pytest.mark.asyncio
    async def test_webhook_error_handling(self, test_client):
        """Test webhook error handling and recovery."""
        # Simulate error by sending malformed JSON
        response = test_client.post(
            "/webhook/sms",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # FastAPI validation error


class TestContextPreservationIntegration:
    """Integration tests specifically for context preservation."""
    
    @pytest.mark.asyncio
    async def test_llm_receives_conversation_history(self, test_client, sample_team_member):
        """Test that LLM processor receives complete conversation history."""
        mock_processor = AsyncMock()
        mock_processor.process_command_with_llm.return_value = "Processed with context"
        
        with patch('app.services.command_processor', mock_processor):
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Send multiple messages
            messages = [
                "Can we schedule a meeting?",
                "How about tomorrow?", 
                "At 2pm would be good"
            ]
            
            for message in messages:
                payload = {**base_payload, "data": {**base_payload["data"], "body": message}}
                test_client.post("/webhook/sms", json=payload)
            
            # Verify LLM was called with conversation context
            assert mock_processor.process_command_with_llm.call_count == 3
            
            # Check the last call had conversation with history
            last_call = mock_processor.process_command_with_llm.call_args_list[-1]
            conversation_arg = last_call[1]['conversation']  # keyword argument
            
            assert conversation_arg is not None
            assert 'recent_messages' in conversation_arg.context
            assert len(conversation_arg.context['recent_messages']) == 3
    
    @pytest.mark.asyncio
    async def test_conversation_context_with_pending_state(self, test_client, test_db_session, sample_team_member):
        """Test conversation context with pending confirmation state."""
        from database.models import Conversation
        
        # Create conversation with pending state
        conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "recent_messages": [
                    {"message": "Schedule family dinner", "timestamp": datetime.utcnow().isoformat()}
                ],
                "pending_confirmation": {
                    "type": "meeting_time",
                    "details": {
                        "title": "Family Dinner",
                        "proposed_time": "2024-01-15T19:00:00"
                    }
                }
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        mock_processor = AsyncMock()
        mock_processor.process_command_with_llm.return_value = "Dinner scheduled!"
        
        with patch('app.services.command_processor', mock_processor):
            # Send confirmation message
            payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="Yes, that works for me",
                first_name="John",
                last_name="Doe"
            )
            
            response = test_client.post("/webhook/sms", json=payload)
            assert response.status_code == 200
            
            # Verify LLM received the pending confirmation context
            call_args = mock_processor.process_command_with_llm.call_args
            conversation_arg = call_args[1]['conversation']
            
            assert 'pending_confirmation' in conversation_arg.context
            assert conversation_arg.context['pending_confirmation']['type'] == 'meeting_time'
    
    @pytest.mark.asyncio
    async def test_conversation_context_timeout_handling(self, test_client, test_db_session, sample_team_member):
        """Test handling of stale conversation context."""
        from database.models import Conversation
        
        # Create old conversation (simulate timeout)
        old_conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "recent_messages": [
                    {"message": "Old message", "timestamp": (datetime.utcnow() - timedelta(hours=24)).isoformat()}
                ],
                "last_intent": "schedule_meeting"
            },
            last_activity=datetime.utcnow() - timedelta(hours=24)
        )
        test_db_session.add(old_conversation)
        test_db_session.commit()
        
        mock_processor = AsyncMock()
        mock_processor.process_command_with_llm.return_value = "Fresh conversation"
        
        with patch('app.services.command_processor', mock_processor):
            # Send new message after long delay
            payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="Hello again",
                first_name="John",
                last_name="Doe"
            )
            
            response = test_client.post("/webhook/sms", json=payload)
            assert response.status_code == 200
            
            # Verify conversation context was updated
            updated_conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert len(updated_conversation.context["recent_messages"]) == 2  # Old + new
            assert updated_conversation.context["recent_messages"][-1]["message"] == "Hello again"


class TestMultiUserContextIsolation:
    """Test that conversation contexts are properly isolated between users."""
    
    @pytest.mark.asyncio
    async def test_separate_user_contexts(self, test_client, test_db_session, sample_team):
        """Test that different users have separate conversation contexts."""
        from database.models import TeamMember, Conversation
        
        # Create two different users
        user1 = TeamMember(
            team_id=sample_team.id,
            name="User One",
            phone="+15551111111"
        )
        user2 = TeamMember(
            team_id=sample_team.id,
            name="User Two", 
            phone="+15552222222"
        )
        test_db_session.add_all([user1, user2])
        test_db_session.commit()
        
        mock_processor = AsyncMock()
        mock_processor.process_command_with_llm.return_value = "Processed"
        
        with patch('app.services.command_processor', mock_processor):
            # User 1 sends messages
            for i, message in enumerate(["User 1 message 1", "User 1 message 2"]):
                payload = create_sms_payload(
                    phone_number=user1.phone,
                    message=message,
                    first_name="User",
                    last_name="One"
                )
                test_client.post("/webhook/sms", json=payload)
            
            # User 2 sends messages
            for i, message in enumerate(["User 2 message 1", "User 2 message 2"]):
                payload = create_sms_payload(
                    phone_number=user2.phone,
                    message=message,
                    first_name="User",
                    last_name="Two"
                )
                test_client.post("/webhook/sms", json=payload)
        
        # Verify separate conversations
        conv1 = test_db_session.query(Conversation).filter(
            Conversation.phone_number == user1.phone
        ).first()
        conv2 = test_db_session.query(Conversation).filter(
            Conversation.phone_number == user2.phone
        ).first()
        
        assert conv1.id != conv2.id
        assert len(conv1.context["recent_messages"]) == 2
        assert len(conv2.context["recent_messages"]) == 2
        assert conv1.context["recent_messages"][0]["message"] == "User 1 message 1"
        assert conv2.context["recent_messages"][0]["message"] == "User 2 message 1"