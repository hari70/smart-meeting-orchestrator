"""
Integration tests to verify SMS context preservation fix.
"""
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from tests.conftest import create_sms_payload


class TestContextPreservationFix:
    """Test that the context preservation fix resolves SMS conversation issues."""
    
    @pytest.mark.asyncio
    async def test_conversation_context_preserved_in_llm_prompt(self, test_client, test_db_session, sample_team_member):
        """Test that conversation history is properly included in LLM prompts."""
        from database.models import Conversation
        
        # Mock the LLM processor to capture the prompts it receives
        mock_processor = AsyncMock()
        captured_prompts = []
        
        async def capture_llm_call(**kwargs):
            captured_prompts.append(kwargs.get('conversation'))
            return "I understand the context!"
        
        mock_processor.process_command_with_llm = capture_llm_call
        
        with patch('app.services.command_processor', mock_processor):
            base_payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="",
                first_name="John",
                last_name="Doe"
            )
            
            # Sequential messages to build context
            messages = [
                "Can we schedule a family meeting?",
                "How about tomorrow?",
                "At 2pm would be perfect",
                "Yes, that sounds great"
            ]
            
            for i, message in enumerate(messages):
                payload = {**base_payload, "data": {**base_payload["data"], "body": message}}
                response = test_client.post("/webhook/sms", json=payload)
                assert response.status_code == 200
            
            # Check that each LLM call received proper conversation context
            assert len(captured_prompts) == 4
            
            # First message should have no history
            first_conversation = captured_prompts[0]
            assert len(first_conversation.context.get("recent_messages", [])) == 1
            
            # Fourth message should have full history
            fourth_conversation = captured_prompts[3]
            assert len(fourth_conversation.context["recent_messages"]) == 4
            
            # Verify context includes intent tracking
            assert "last_intent" in fourth_conversation.context
            
            # Verify messages are properly ordered
            recent_messages = fourth_conversation.context["recent_messages"]
            assert recent_messages[0]["message"] == "Can we schedule a family meeting?"
            assert recent_messages[3]["message"] == "Yes, that sounds great"
    
    @pytest.mark.asyncio
    async def test_intent_detection_and_tracking(self, test_client, test_db_session, sample_team_member):
        """Test that message intents are properly detected and tracked."""
        from database.models import Conversation
        
        base_payload = create_sms_payload(
            phone_number=sample_team_member.phone,
            message="",
            first_name="John", 
            last_name="Doe"
        )
        
        # Test different intent types
        test_cases = [
            ("Can we schedule a meeting?", "schedule_meeting"),
            ("Yes, that works for me", "confirmation"),
            ("How about tomorrow at 2pm?", "time_specification"),
            ("What meetings do I have?", "query"),
            ("Cancel that meeting", "cancellation")
        ]
        
        for message, expected_intent in test_cases:
            payload = {**base_payload, "data": {**base_payload["data"], "body": message}}
            response = test_client.post("/webhook/sms", json=payload)
            assert response.status_code == 200
            
            # Check conversation context was updated with intent
            conversation = test_db_session.query(Conversation).filter(
                Conversation.phone_number == sample_team_member.phone
            ).first()
            
            assert conversation.context["last_intent"] == expected_intent
            assert conversation.context["message_count"] > 0
    
    @pytest.mark.asyncio
    async def test_pending_confirmation_handling(self, test_client, test_db_session, sample_team_member):
        """Test that pending confirmations are properly handled."""
        from database.models import Conversation
        
        # Create conversation with pending confirmation
        conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "pending_confirmation": {
                    "type": "meeting_time",
                    "details": {
                        "title": "Family Meeting",
                        "proposed_time": "2024-01-15T14:00:00"
                    },
                    "awaiting_response": True
                }
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        mock_processor = AsyncMock()
        captured_conversations = []
        
        async def capture_conversation(**kwargs):
            captured_conversations.append(kwargs.get('conversation'))
            return "Meeting confirmed!"
        
        mock_processor.process_command_with_llm = capture_conversation
        
        with patch('app.services.command_processor', mock_processor):
            # Send confirmation response
            payload = create_sms_payload(
                phone_number=sample_team_member.phone,
                message="Yes, that works",
                first_name="John",
                last_name="Doe"
            )
            
            response = test_client.post("/webhook/sms", json=payload)
            assert response.status_code == 200
            
            # Verify pending confirmation was passed to LLM
            assert len(captured_conversations) == 1
            conv = captured_conversations[0]
            assert "pending_confirmation" in conv.context
            assert conv.context["pending_confirmation"]["type"] == "meeting_time"
    
    @pytest.mark.asyncio
    async def test_enhanced_llm_prompt_structure(self, test_client, test_db_session, sample_team_member):
        """Test that LLM prompts include enhanced context structure."""
        from llm_integration.enhanced_command_processor import LLMCommandProcessor
        from database.models import Conversation
        
        # Create rich conversation context
        conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "recent_messages": [
                    {"message": "Can we schedule something?", "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat()},
                    {"message": "How about a family dinner?", "timestamp": (datetime.utcnow() - timedelta(minutes=3)).isoformat()},
                    {"message": "Tomorrow would be good", "timestamp": (datetime.utcnow() - timedelta(minutes=1)).isoformat()}
                ],
                "last_intent": "schedule_meeting",
                "pending_confirmation": {
                    "type": "meeting_time",
                    "details": {"title": "Family Dinner", "proposed_time": "tomorrow evening"}
                }
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Create LLM processor and test prompt generation
        processor = LLMCommandProcessor(None, None, None, None)
        
        # Test _create_user_prompt method directly
        prompt = processor._create_user_prompt(
            message_text="Yes, 7pm works",
            team_member=sample_team_member,
            conversation=conversation
        )
        
        # Verify prompt structure
        assert "CONVERSATION HISTORY" in prompt
        assert "PENDING CONFIRMATION" in prompt
        assert "Can we schedule something?" in prompt
        assert "Family Dinner" in prompt
        assert "Last detected intent: schedule_meeting" in prompt
        assert "CONTEXT ANALYSIS" in prompt
        assert "If this continues a previous conversation" in prompt
    
    @pytest.mark.asyncio
    async def test_new_topic_detection_clears_pending_state(self, test_client, test_db_session, sample_team_member):
        """Test that new topics clear old pending confirmation state."""
        from database.models import Conversation
        
        # Create conversation with pending state
        conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "recent_messages": [
                    {"message": "Schedule dinner tomorrow?", "timestamp": datetime.utcnow().isoformat()}
                ],
                "pending_confirmation": {
                    "type": "meeting_time",
                    "details": {"title": "Dinner"},
                    "awaiting_response": True
                }
            }
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Send message indicating new topic
        payload = create_sms_payload(
            phone_number=sample_team_member.phone,
            message="Actually, let's schedule a different meeting",  # New topic
            first_name="John",
            last_name="Doe"
        )
        
        response = test_client.post("/webhook/sms", json=payload)
        assert response.status_code == 200
        
        # Check that pending confirmation was cleared
        updated_conversation = test_db_session.query(Conversation).filter(
            Conversation.phone_number == sample_team_member.phone
        ).first()
        
        # Pending confirmation should be cleared due to new topic
        assert "pending_confirmation" not in updated_conversation.context
        assert updated_conversation.context["last_intent"] == "schedule_meeting"
    
    @pytest.mark.asyncio
    async def test_conversation_timeout_handling(self, test_client, test_db_session, sample_team_member):
        """Test handling of conversations with time gaps."""
        from database.models import Conversation
        
        # Create old conversation
        old_time = datetime.utcnow() - timedelta(hours=2)
        conversation = Conversation(
            phone_number=sample_team_member.phone,
            team_id=sample_team_member.team_id,
            context={
                "recent_messages": [
                    {"message": "Old message", "timestamp": old_time.isoformat()}
                ],
                "last_intent": "schedule_meeting",
                "message_count": 1
            },
            last_activity=old_time
        )
        test_db_session.add(conversation)
        test_db_session.commit()
        
        # Send new message after long gap
        payload = create_sms_payload(
            phone_number=sample_team_member.phone,
            message="Hello again",
            first_name="John",
            last_name="Doe"
        )
        
        response = test_client.post("/webhook/sms", json=payload)
        assert response.status_code == 200
        
        # Check conversation context includes both old and new
        updated_conversation = test_db_session.query(Conversation).filter(
            Conversation.phone_number == sample_team_member.phone
        ).first()
        
        assert len(updated_conversation.context["recent_messages"]) == 2
        assert updated_conversation.context["message_count"] == 2
        assert updated_conversation.context["recent_messages"][-1]["message"] == "Hello again"