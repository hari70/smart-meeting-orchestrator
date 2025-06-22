# main.py - SMS Coordination MCP Server
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
    create_tables()
    logger.info("🚀 Smart Meeting Orchestrator MCP Server started successfully")

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

@app.post("/webhook/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Main webhook endpoint for incoming SMS messages from Surge
    """
    try:
        # Parse incoming webhook payload
        payload = await request.json()
        logger.info(f"🎯 STEP 1: Received Surge SMS webhook: {payload}")
        
        # Extract SMS data from Surge webhook format
        event = payload.get("type", "")  # Surge uses 'type', not 'event'
        if event != "message.received":
            logger.info(f"STEP 1B: Ignoring webhook event: {event}")
            return JSONResponse(status_code=200, content={"status": "ignored"})
        
        message_data = payload.get("data", {})  # Surge uses 'data', not 'message'
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        
        from_number = contact_data.get("phone_number", "").strip()
        message_text = message_data.get("body", "").strip()
        message_id = message_data.get("id", "")
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        
        logger.info(f"📱 STEP 2: Extracted SMS data - From: {from_number}, Message: '{message_text}', Name: {first_name} {last_name}")
        
        if not from_number or not message_text:
            logger.warning("❌ STEP 2 FAILED: Invalid Surge SMS webhook payload received")
            logger.warning(f"   Phone: '{from_number}', Message: '{message_text}'")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid SMS payload"}
            )
        
        # Normalize phone number
        from_number = normalize_phone_number(from_number)
        logger.info(f"📞 STEP 3: Normalized phone: {from_number}")
        
        # Process the SMS command
        logger.info(f"🔄 STEP 4: Starting SMS command processing...")
        response = await process_sms_command(
            from_number=from_number,
            message_text=message_text,
            first_name=first_name,
            last_name=last_name,
            db=db
        )
        
        logger.info(f"✅ STEP 5: SMS processing complete. Response: '{response}'")
        
        # Send response back via SMS
        if response:
            logger.info(f"📤 STEP 6: Attempting to send SMS response...")
            
            # Check SMS credentials first
            api_key = os.getenv("SURGE_SMS_API_KEY")
            account_id = os.getenv("SURGE_ACCOUNT_ID")
            
            if not api_key or not account_id:
                logger.error("❌ STEP 6 FAILED: SMS credentials not configured!")
                logger.error(f"API Key present: {bool(api_key)}")
                logger.error(f"Account ID present: {bool(account_id)}")
            else:
                success = await surge_client.send_message(from_number, response, first_name, last_name)
                logger.info(f"📨 STEP 7: SMS response sent successfully: {success}")
                
                if not success:
                    logger.error(f"❌ STEP 7 FAILED: Could not send SMS response")
        
        return JSONResponse(
            status_code=200,
            content={"status": "processed", "message_id": message_id}
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing Surge SMS webhook: {str(e)}")
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
        
        # Process command using CommandProcessor
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
            is_admin=False  # First user becomes admin later
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
    """
    Get existing conversation or create new one
    """
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
    """
    Get team member by phone number
    """
    return db.query(TeamMember).filter(
        TeamMember.phone == phone_number
    ).first()

def update_conversation_context(conversation: Conversation, message: str, db: Session):
    """
    Update conversation context with latest message
    """
    if not conversation.context:
        conversation.context = {}
    
    # Store last few messages for context
    messages = conversation.context.get("recent_messages", [])
    messages.append({
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Keep only last 5 messages
    conversation.context["recent_messages"] = messages[-5:]
    conversation.last_activity = datetime.utcnow()
    
    db.commit()

def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to consistent format
    """
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+1' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned

def extract_name_from_message(message: str) -> str:
    """
    Extract name from onboarding message
    """
    message = message.lower()
    
    # Common patterns
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
            # Remove common words
            name = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', name, flags=re.IGNORECASE)
            return name.strip()
    
    return None

# API endpoints for manual management

@app.get("/teams")
async def list_teams(db: Session = Depends(get_db)):
    """List all teams"""
    teams = db.query(Team).all()
    return [{"id": str(team.id), "name": team.name} for team in teams]

@app.get("/teams/{team_id}/members")
async def list_team_members(team_id: str, db: Session = Depends(get_db)):
    """List team members"""
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    return [
        {
            "id": str(member.id),
            "name": member.name,
            "phone": member.phone,
            "is_admin": member.is_admin
        }
        for member in members
    ]

@app.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    member_data: dict,
    db: Session = Depends(get_db)
):
    """Manually add team member"""
    member = TeamMember(
        team_id=team_id,
        name=member_data["name"],
        phone=normalize_phone_number(member_data["phone"]),
        google_calendar_id=member_data.get("google_calendar_id"),
        is_admin=member_data.get("is_admin", False)
    )
    
    db.add(member)
    db.commit()
    
    return {"message": "Member added successfully", "id": str(member.id)}

@app.get("/meetings")
async def list_meetings(db: Session = Depends(get_db)):
    """List recent meetings"""
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(10).all()
    return [
        {
            "id": str(meeting.id),
            "title": meeting.title,
            "scheduled_time": meeting.scheduled_time.isoformat() if meeting.scheduled_time else None,
            "google_meet_link": meeting.google_meet_link
        }
        for meeting in meetings
    ]

@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration"""
    return {
        "surge_api_key_present": bool(os.getenv("SURGE_SMS_API_KEY")),
        "surge_account_id_present": bool(os.getenv("SURGE_ACCOUNT_ID")),
        "database_url_present": bool(os.getenv("DATABASE_URL")),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT"),
        "port": os.getenv("PORT", "8000")
    }

@app.post("/test/sms")
async def test_sms_send(request: Request):
    """Test endpoint to debug SMS sending"""
    try:
        data = await request.json()
        to_number = data.get("to_number")
        message = data.get("message", "Test message from MCP SMS Orchestrator!")
        first_name = data.get("first_name", "Test")
        last_name = data.get("last_name", "User")
        
        logger.info(f"🧪 TEST SMS REQUEST: {data}")
        
        if not to_number:
            return JSONResponse(
                status_code=400,
                content={"error": "to_number is required"}
            )
        
        # Normalize phone number
        normalized_number = normalize_phone_number(to_number)
        logger.info(f"📞 Normalized number: {to_number} → {normalized_number}")
        
        # Check credentials
        api_key = os.getenv("SURGE_SMS_API_KEY")
        account_id = os.getenv("SURGE_ACCOUNT_ID")
        
        logger.info(f"🔑 Credentials check:")
        logger.info(f"   API Key present: {bool(api_key)}")
        logger.info(f"   Account ID present: {bool(account_id)}")
        
        if not api_key or not account_id:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "SMS credentials not configured",
                    "api_key_present": bool(api_key),
                    "account_id_present": bool(account_id)
                }
            )
        
        # Send test SMS
        success = await surge_client.send_message(normalized_number, message, first_name, last_name)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": success,
                "message_sent": message,
                "to_number": normalized_number,
                "api_key_present": bool(api_key),
                "account_id_present": bool(account_id)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Test SMS error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))