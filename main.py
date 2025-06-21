# main_working.py - Back to proven working version
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import json
import logging
from datetime import datetime, timedelta
import re

# Local imports
from database.connection import get_db, create_tables
from database.models import Team, TeamMember, Meeting, Conversation
from sms_coordinator.surge_client import SurgeSMSClient
from sms_coordinator.command_processor import CommandProcessor
from google_integrations.calendar_client import GoogleCalendarClient
from google_integrations.meet_client import GoogleMeetClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Smart Meeting Orchestrator",
    description="SMS-based meeting coordination using MCP architecture",
    version="1.0.0"
)

# Initialize clients
surge_client = SurgeSMSClient(
    api_key=os.getenv("SURGE_SMS_API_KEY"),
    account_id=os.getenv("SURGE_ACCOUNT_ID")
)

calendar_client = GoogleCalendarClient()
meet_client = GoogleMeetClient()
command_processor = CommandProcessor(surge_client, calendar_client, meet_client)

@app.on_event("startup")
async def startup_event():
    """Initialize database and load initial data"""
    try:
        create_tables()
        logger.info("Smart Meeting Orchestrator started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        pass

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Smart Meeting Orchestrator MCP Server",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/debug/env")
async def debug_env():
    """Debug endpoint to check environment variables"""
    api_key = os.getenv("SURGE_SMS_API_KEY", "NOT_SET")
    account_id = os.getenv("SURGE_ACCOUNT_ID", "NOT_SET")
    database_url = os.getenv("DATABASE_URL", "NOT_SET")
    
    return {
        "api_key_present": bool(api_key and api_key != "NOT_SET"),
        "account_id_present": bool(account_id and account_id != "NOT_SET"),
        "database_url_present": bool(database_url and database_url != "NOT_SET"),
        "version": "working_stable"
    }

@app.post("/webhook/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Main webhook endpoint for incoming SMS messages from Surge
    """
    try:
        # Parse incoming webhook payload
        payload = await request.json()
        logger.info(f"Received Surge SMS webhook: {payload}")
        
        # Extract SMS data from ACTUAL Surge webhook format
        event_type = payload.get("type", "")
        if event_type != "message.received":
            logger.info(f"Ignoring webhook event: {event_type}")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        # Surge puts data in "data" not "message"
        message_data = payload.get("data", {})
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        
        from_number = contact_data.get("phone_number", "").strip()
        message_text = message_data.get("body", "").strip()
        message_id = message_data.get("id", "")
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        
        if not from_number or not message_text:
            logger.warning("Invalid Surge SMS webhook payload received")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid SMS payload"}
            )
        
        logger.info(f"Processing SMS from {from_number}: {message_text}")
        
        # Normalize phone number
        from_number = normalize_phone_number(from_number)
        
        # Process the SMS command using the working command processor
        response = await process_sms_command(
            from_number=from_number,
            message_text=message_text,
            first_name=first_name,
            last_name=last_name,
            db=db
        )
        
        # Send response back via SMS
        if response:
            logger.info(f"Sending response SMS to {from_number}: {response}")
            await surge_client.send_message(from_number, response, first_name, last_name)
        
        return JSONResponse(
            status_code=200,
            content={"status": "processed", "message_id": message_id}
        )
        
    except Exception as e:
        logger.error(f"Error processing Surge SMS webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

async def process_sms_command(from_number: str, message_text: str, first_name: str, last_name: str, db: Session):
    """
    Process incoming SMS command and route to appropriate handler
    """
    try:
        # Get or create conversation context
        conversation = get_or_create_conversation(from_number, db)
        
        # Get team member info
        team_member = get_team_member_by_phone(from_number, db)
        
        if not team_member:
            # New user - guide them through setup
            return await handle_new_user(from_number, message_text, first_name, last_name, db)
        
        # Update conversation context
        update_conversation_context(conversation, message_text, db)
        
        # Process command using proven CommandProcessor
        response = await command_processor.process_command(
            message_text=message_text,
            team_member=team_member,
            conversation=conversation,
            db=db
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing command from {from_number}: {str(e)}")
        return "Sorry, I encountered an error processing your request. Please try again."

async def handle_new_user(from_number: str, message_text: str, first_name: str, last_name: str, db: Session):
    """
    Handle new user onboarding with name from Surge contact data
    """
    # If we have first/last name from Surge contact, use that
    if first_name or last_name:
        full_name = f"{first_name} {last_name}".strip()
        return await create_new_user(from_number, full_name, db)
    
    # Otherwise, use original flow
    welcome_message = """
🎉 Welcome to Smart Meeting Orchestrator!

I can help you coordinate family meetings via SMS. To get started, I need to add you to a team.

Please reply with your name and I'll set you up!

Example: "My name is John Smith"
    """.strip()
    
    # Check if they're providing their name
    if "name is" in message_text.lower() or "i'm" in message_text.lower():
        return await create_new_user(from_number, message_text, db)
    
    return welcome_message

async def create_new_user(from_number: str, name_input: str, db: Session):
    """
    Create new user and add them to default family team
    """
    try:
        # Extract or use provided name
        if "name is" in name_input.lower() or "i'm" in name_input.lower():
            name = extract_name_from_message(name_input)
        else:
            name = name_input.strip()
        
        if not name:
            return "I couldn't understand your name. Please try: 'My name is [Your Name]'"
        
        # Get or create default family team
        team = db.query(Team).filter(Team.name == "Family").first()
        if not team:
            team = Team(name="Family")
            db.add(team)
            db.commit()
            db.refresh(team)
        
        # Create team member
        team_member = TeamMember(
            team_id=team.id,
            name=name,
            phone=from_number,
            is_admin=False
        )
        
        db.add(team_member)
        db.commit()
        
        # If this is the first team member, make them admin
        member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
        if member_count == 1:
            team_member.is_admin = True
            db.commit()
        
        return f"""
✅ Welcome {name}! You've been added to the Family team.

Here are some things you can try:
• "Family meeting about vacation this weekend"
• "Schedule call with everyone next week"
• "What's our next meeting?"

I can coordinate with Google Calendar and create Google Meet links automatically!
        """.strip()
        
    except Exception as e:
        logger.error(f"Error creating new user: {str(e)}")
        return "Sorry, there was an error setting up your account. Please try again."

def get_or_create_conversation(phone_number: str, db: Session) -> Conversation:
    """Get existing conversation or create new one"""
    conversation = db.query(Conversation).filter(
        Conversation.phone_number == phone_number
    ).first()
    
    if not conversation:
        conversation = Conversation(
            phone_number=phone_number,
            context={},
            last_activity=datetime.utcnow()
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    return conversation

def get_team_member_by_phone(phone_number: str, db: Session) -> TeamMember:
    """Get team member by phone number"""
    return db.query(TeamMember).filter(
        TeamMember.phone == phone_number
    ).first()

def update_conversation_context(conversation: Conversation, message: str, db: Session):
    """Update conversation context with latest message"""
    if not conversation.context:
        conversation.context = {}
    
    messages = conversation.context.get("recent_messages", [])
    messages.append({
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    conversation.context["recent_messages"] = messages[-5:]
    conversation.last_activity = datetime.utcnow()
    db.commit()

def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to consistent format"""
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if not cleaned.startswith('+'):
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+1' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned

def extract_name_from_message(message: str) -> str:
    """Extract name from onboarding message"""
    message = message.lower()
    
    patterns = [
        r"name is ([a-zA-Z\s]+)",
        r"i'm ([a-zA-Z\s]+)",
        r"i am ([a-zA-Z\s]+)",
        r"call me ([a-zA-Z\s]+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            name = match.group(1).strip().title()
            name = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', name, flags=re.IGNORECASE)
            return name.strip()
    
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
