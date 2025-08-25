from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
import re
from datetime import datetime

from database.connection import get_db, create_tables
from database.models import Team, TeamMember, Conversation
from app import services

router = APIRouter(prefix="/webhook", tags=["webhook"])
logger = logging.getLogger(__name__)


@router.post("/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        logger.info(f"Incoming SMS webhook: {payload}")
        event = payload.get("type", "")
        if event != "message.received":
            return {"status": "ignored"}
        message_data = payload.get("data", {})
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        from_number = contact_data.get("phone_number", "").strip()
        message_text = message_data.get("body", "").strip()
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        if not from_number or not message_text:
            return JSONResponse(status_code=400, content={"error": "Invalid SMS payload"})
        from_number = _normalize_phone(from_number)
        response = await _process_sms_command(from_number, message_text, first_name, last_name, db)
        if response:
            await services.surge_client.send_message(from_number, response, first_name, last_name)
        return {"status": "processed"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


async def _process_sms_command(from_number: str, message_text: str, first_name: str, last_name: str, db: Session):
    conversation = _get_or_create_conversation(from_number, db)
    member = _get_team_member_by_phone(from_number, db)
    if not member:
        return await _handle_new_user(from_number, message_text, first_name, last_name, db)
    _update_conversation_context(conversation, message_text, db)
    
    # Temporary fallback for testing - bypass LLM issues
    try:
        return await services.command_processor.process_command_with_llm(
            message_text=message_text,
            team_member=member,
            conversation=conversation,
            db=db
        )
    except Exception as e:
        logger.error(f"LLM processing failed: {e}")
        # Simple fallback response for testing
        if "schedule" in message_text.lower() and "meeting" in message_text.lower():
            return "I'd help you schedule that meeting! (LLM temporarily unavailable - this is a test response)"
        elif "list" in message_text.lower() or "meetings" in message_text.lower():
            return "Here are your upcoming meetings: (No meetings found - LLM temporarily unavailable)"
        else:
            return "I'm here to help with meeting coordination! (LLM temporarily unavailable - please try again later)"


async def _handle_new_user(from_number: str, message_text: str, first_name: str, last_name: str, db: Session):
    if first_name or last_name:
        full_name = f"{first_name} {last_name}".strip()
        return await _create_new_user(from_number, full_name, db)
    if "name is" in message_text.lower() or "i'm" in message_text.lower():
        return await _create_new_user(from_number, message_text, db)
    return ("🎉 Welcome! Reply with your name to join. Example: 'My name is John Smith'")


async def _create_new_user(from_number: str, name_input: str, db: Session):
    name = _extract_name_from_message(name_input) or name_input.strip()
    if not name:
        return "I couldn't understand your name. Try: 'My name is [Your Name]'"
    team = db.query(Team).filter(Team.name == "Family").first()
    if not team:
        team = Team(name="Family")
        db.add(team)
        db.commit()
        db.refresh(team)
    member = TeamMember(team_id=team.id, name=name, phone=from_number, is_admin=False)
    db.add(member)
    db.commit()
    count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    if count == 1:
        member.is_admin = True
        db.commit()
    return (f"✅ Welcome {name}! You're added to Family. Try: 'Family meeting about vacation this weekend'")


def _get_or_create_conversation(phone_number: str, db: Session) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.phone_number == phone_number).first()
    if not conversation:
        conversation = Conversation(phone_number=phone_number, context={}, last_activity=datetime.utcnow())
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def _get_team_member_by_phone(phone_number: str, db: Session) -> TeamMember:
    return db.query(TeamMember).filter(TeamMember.phone == phone_number).first()


def _update_conversation_context(conversation: Conversation, message: str, db: Session):
    """Update conversation context with enhanced state tracking."""
    if not conversation.context:
        conversation.context = {}
    
    # Update recent messages
    msgs = conversation.context.get("recent_messages", [])
    msgs.append({
        "message": message, 
        "timestamp": datetime.utcnow().isoformat()
    })
    conversation.context["recent_messages"] = msgs[-5:]  # Keep last 5 messages
    
    # Detect and track intent from message
    intent = _detect_message_intent(message)
    if intent:
        conversation.context["last_intent"] = intent
        logger.info(f"🎯 [INTENT] Detected intent: {intent} from message: '{message[:50]}...'")
    
    # Track conversation state for better context
    conversation.context["message_count"] = conversation.context.get("message_count", 0) + 1
    conversation.context["last_message_time"] = datetime.utcnow().isoformat()
    
    # Clear old pending confirmations if user starts new topic
    if _is_new_topic(message) and "pending_confirmation" in conversation.context:
        logger.info(f"🔄 [CONTEXT] Clearing old pending confirmation - new topic detected")
        del conversation.context["pending_confirmation"]
    
    conversation.last_activity = datetime.utcnow()
    db.commit()
    
    logger.info(f"📚 [CONTEXT] Updated conversation context: {len(msgs)} messages, intent: {intent}")


def _detect_message_intent(message: str) -> str:
    """Detect the intent of a message for context tracking."""
    message_lower = message.lower().strip()
    
    # Scheduling intents
    if any(word in message_lower for word in ['schedule', 'meeting', 'event', 'book', 'plan']):
        return 'schedule_meeting'
    
    # Confirmation intents
    if any(word in message_lower for word in ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'sounds good', 'that works']):
        return 'confirmation'
    
    # Denial intents
    if any(word in message_lower for word in ['no', 'nope', 'nah', 'not', "can't", "won't"]):
        return 'denial'
    
    # Time specification
    if any(word in message_lower for word in ['tomorrow', 'today', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'pm', 'am', 'at']):
        return 'time_specification'
    
    # Query intents
    if any(word in message_lower for word in ['when', 'what', 'where', 'who', 'how', 'list', 'show']):
        return 'query'
    
    # Cancellation intents
    if any(word in message_lower for word in ['cancel', 'delete', 'remove', 'stop']):
        return 'cancellation'
    
    return 'general'


def _is_new_topic(message: str) -> bool:
    """Determine if message indicates a new conversation topic."""
    message_lower = message.lower().strip()
    
    # Clear topic change indicators
    new_topic_phrases = [
        'new topic', 'different topic', 'something else', 'also', 'by the way',
        'btw', 'another thing', 'one more thing', 'oh and', 'actually'
    ]
    
    # Direct scheduling requests usually indicate new topics
    scheduling_starters = [
        'schedule', 'can we', 'let\'s', 'how about', 'what about', 'i need to'
    ]
    
    return (any(phrase in message_lower for phrase in new_topic_phrases) or
            any(message_lower.startswith(starter) for starter in scheduling_starters))


def _normalize_phone(phone: str) -> str:
    cleaned = re.sub(r'[^\d+]', '', phone)
    if not cleaned.startswith('+'):
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+1' + cleaned
        else:
            cleaned = '+' + cleaned
    return cleaned


def _extract_name_from_message(message: str):
    m = message.lower()
    patterns = [r"name is ([a-zA-Z\s]+)", r"i'm ([a-zA-Z\s]+)", r"i am ([a-zA-Z\s]+)", r"call me ([a-zA-Z\s]+)"]
    import re as _re
    for p in patterns:
        match = _re.search(p, m)
        if match:
            name = match.group(1).strip().title()
            name = _re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', name, flags=_re.IGNORECASE)
            return name.strip()
    return None
