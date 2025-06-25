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
from llm_integration.enhanced_command_processor import LLMCommandProcessor
from mcp_integration.mcp_command_processor import MCPCommandProcessor
from google_integrations.calendar_client import GoogleCalendarClient
from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
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

# Initialize calendar client - ALWAYS use Direct Google API (MCP removed)
# Since MCP tools aren't working reliably, use direct Google Calendar API with Railway credentials
calendar_client = DirectGoogleCalendarClient()
logger.info("🔗 Using DIRECT Google Calendar API only (MCP disabled)")

meet_client = GoogleMeetClient()
strava_client = None  # Will add Strava integration later

# Use standard LLM command processor since we're using Direct Google API
command_processor = LLMCommandProcessor(surge_client, calendar_client, meet_client, strava_client)
logger.info("🤖 Using standard LLM Command Processor with Direct Google Calendar API")

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
        logger.info(f"🔍 [SMS DEBUG] Raw message text received: '{message_text}'")
        
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
        
        # Process command using Enhanced LLM CommandProcessor
        response = await command_processor.process_command_with_llm(
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

@app.get("/debug/mcp-status")
async def debug_mcp_status():
    """Debug endpoint to check MCP integration status"""
    try:
        return {
            "mcp_integration": {
                "use_real_mcp_calendar": os.getenv("USE_REAL_MCP_CALENDAR") == "true",
                "calendar_client_type": type(calendar_client).__name__,
                "command_processor_type": type(command_processor).__name__,
                "mcp_calendar_available": hasattr(calendar_client, 'mcp_enabled') and getattr(calendar_client, 'mcp_enabled', False),
                "anthropic_api_available": bool(os.getenv("ANTHROPIC_API_KEY")),
                "available_mcp_tools": getattr(calendar_client, 'get_available_tools', lambda: [])() if hasattr(calendar_client, 'get_available_tools') else []
            },
            "current_configuration": {
                "integration_mode": "Real MCP Calendar" if os.getenv("USE_REAL_MCP_CALENDAR") == "true" else "Mock Calendar",
                "processor_mode": "Aggressive (Forces tool usage)" if type(command_processor).__name__ == "MCPCommandProcessor" else "Standard LLM",
                "will_create_real_events": os.getenv("USE_REAL_MCP_CALENDAR") == "true" and bool(os.getenv("ANTHROPIC_API_KEY"))
            },
            "setup_instructions": {
                "to_enable_real_mcp": "Set USE_REAL_MCP_CALENDAR=true in Railway environment",
                "to_enable_llm_intelligence": "Set ANTHROPIC_API_KEY=your_claude_key in Railway environment",
                "your_mcp_tools": "You mentioned having 8 Google Calendar MCP tools - this will connect to them"
            },
            "test_commands": [
                "Schedule family dinner tomorrow at 7pm",
                "What meetings do I have this week?",
                "Plan family meeting about vacation this weekend"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ MCP debug error: {str(e)}")
        return {"error": str(e)}

@app.get("/debug/calendar-status")
async def debug_calendar_status():
    """Debug endpoint to check calendar integration status"""
    try:
        # Check calendar client configuration
        calendar_status = {
            "calendar_client_type": type(calendar_client).__name__,
            "has_mcp_tools": getattr(calendar_client, 'has_mcp_tools', False),
            "mcp_calendar_enabled": os.getenv("ENABLE_MCP_CALENDAR") == "true",
            "google_credentials_available": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")),
            "integration_mode": "real" if os.getenv("ENABLE_MCP_CALENDAR") == "true" else "mock"
        }
        
        # Test calendar creation
        test_start_time = datetime.now() + timedelta(hours=1)
        test_event = await calendar_client.create_event(
            title="Debug Test Event (Will be deleted)",
            start_time=test_start_time,
            duration_minutes=30,
            attendees=[],
            meet_link="https://test.com"
        )
        
        return {
            "calendar_integration": calendar_status,
            "test_event_creation": {
                "success": test_event is not None,
                "event_data": test_event,
                "is_mock": test_event.get("source") == "mock" if test_event else None
            },
            "recommendations": {
                "current_status": "Using mock calendar - events not saved to real Google Calendar" if calendar_status["integration_mode"] == "mock" else "Real calendar integration enabled",
                "to_enable_real_calendar": "Set ENABLE_MCP_CALENDAR=true in Railway environment variables",
                "for_full_google_api": "Follow setup guide in /google_integrations/real_google_calendar.py"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Calendar debug error: {str(e)}")
        return {
            "error": str(e),
            "calendar_client_available": calendar_client is not None
        }

@app.post("/test/create-calendar-event")
async def test_create_calendar_event(request: Request, db: Session = Depends(get_db)):
    """Test endpoint to manually create calendar events"""
    try:
        data = await request.json()
        title = data.get("title", "Test Meeting from API")
        hours_from_now = data.get("hours_from_now", 2)
        
        # Create test event
        start_time = datetime.now() + timedelta(hours=hours_from_now)
        
        logger.info(f"🧪 MANUAL CALENDAR EVENT TEST:")
        logger.info(f"   Title: {title}")
        logger.info(f"   Start: {start_time}")
        
        # Create Google Meet link
        meet_link = await meet_client.create_meeting(title)
        
        # Create calendar event
        event = await calendar_client.create_event(
            title=title,
            start_time=start_time,
            duration_minutes=60,
            attendees=[],
            meet_link=meet_link
        )
        
        return {
            "success": event is not None,
            "event": event,
            "meet_link": meet_link,
            "is_mock_event": event.get("source") == "mock" if event else None,
            "message": "Event created successfully" if event else "Event creation failed"
        }
        
    except Exception as e:
        logger.error(f"❌ Manual calendar test error: {str(e)}")
        return {"error": str(e)}

@app.post("/admin/add-family-member")
async def add_family_member_simple(request: Request, db: Session = Depends(get_db)):
    """Simple endpoint to add family members"""
    try:
        data = await request.json()
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")  # Added email field
        
        if not name or not phone:
            return JSONResponse(
                status_code=400,
                content={"error": "name and phone are required"}
            )
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone)
        
        # Get or create Family team
        team = db.query(Team).filter(Team.name == "Family").first()
        if not team:
            team = Team(name="Family")
            db.add(team)
            db.commit()
            db.refresh(team)
        
        # Check if member already exists
        existing_member = db.query(TeamMember).filter(
            TeamMember.phone == normalized_phone
        ).first()
        
        if existing_member:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"{existing_member.name} with phone {normalized_phone} already exists"
                }
            )
        
        # Create new team member
        member = TeamMember(
            team_id=team.id,
            name=name,
            phone=normalized_phone,
            email=email,  # Include email
            is_admin=data.get("is_admin", False)
        )
        
        db.add(member)
        db.commit()
        db.refresh(member)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "member": {
                    "id": str(member.id),
                    "name": member.name,
                    "phone": member.phone,
                    "team": team.name
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error adding family member: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/admin/family-members")
async def list_family_members(db: Session = Depends(get_db)):
    """List all family members"""
    try:
        team = db.query(Team).filter(Team.name == "Family").first()
        if not team:
            return JSONResponse(
                status_code=404,
                content={"error": "No Family team found"}
            )
        
        members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        
        return JSONResponse(
        status_code=200,
        content={
        "team": team.name,
        "members": [
        {
        "id": str(member.id),
        "name": member.name,
        "phone": member.phone,
        "email": member.email,  # Include email
            "is_admin": member.is_admin
        }
            for member in members
            ]
            }
            )
        
    except Exception as e:
        logger.error(f"❌ Error listing family members: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/admin/migrate-database")
async def migrate_database():
    """Run database migrations"""
    try:
        from database.migrations.add_email_column import add_email_column
        
        success = add_email_column()
        
        if success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "✅ Email column added successfully! You can now add family members with email addresses."
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "❌ Migration failed. Check server logs for details."
                }
            )
            
    except Exception as e:
        logger.error(f"❌ Migration error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/admin/check-database-schema")
async def check_database_schema():
    """Check current database schema"""
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return {"error": "DATABASE_URL not set"}
        
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            # Get team_members table columns
            query = text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'team_members'
                ORDER BY ordinal_position
            """)
            
            result = connection.execute(query)
            columns = [{
                "name": row[0],
                "type": row[1], 
                "nullable": row[2]
            } for row in result]
            
            has_email = any(col["name"] == "email" for col in columns)
            
            return {
                "table": "team_members",
                "columns": columns,
                "has_email_column": has_email,
                "needs_migration": not has_email
            }
            
    except Exception as e:
        logger.error(f"❌ Schema check error: {str(e)}")
        return {"error": str(e)}

@app.get("/debug/google-credentials")
async def debug_google_credentials():
    """Debug Google Calendar credentials in detail"""
    try:
        # Import here to avoid circular imports
        from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
        
        # Create a client and check its state
        client = DirectGoogleCalendarClient()
        
        # Check environment variables directly
        import os
        env_vars = {
            "GOOGLE_CALENDAR_ACCESS_TOKEN": os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN"),
            "GOOGLE_CALENDAR_REFRESH_TOKEN": os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"),
            "GOOGLE_CALENDAR_CLIENT_ID": os.getenv("GOOGLE_CALENDAR_CLIENT_ID"),
            "GOOGLE_CALENDAR_CLIENT_SECRET": os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")
        }
        
        # Safely check token formats without exposing full values
        token_info = {}
        for key, value in env_vars.items():
            if value:
                token_info[key] = {
                    "present": True,
                    "length": len(value),
                    "starts_with": value[:10] if len(value) > 10 else value[:3] + "...",
                    "format_check": {
                        "access_token_format": value.startswith("ya29.") if "ACCESS_TOKEN" in key else None,
                        "refresh_token_format": value.startswith("1//") if "REFRESH_TOKEN" in key else None,
                        "client_id_format": value.endswith(".apps.googleusercontent.com") if "CLIENT_ID" in key else None
                    }
                }
            else:
                token_info[key] = {"present": False}
        
        return {
            "client_enabled": client.enabled,
            "client_access_token_present": bool(client.access_token),
            "client_refresh_token_present": bool(client.refresh_token),
            "client_client_id_present": bool(client.client_id),
            "client_client_secret_present": bool(client.client_secret),
            "environment_variables": token_info,
            "diagnosis": {
                "has_access_token": bool(client.access_token),
                "has_refresh_credentials": bool(client.refresh_token and client.client_id and client.client_secret),
                "should_be_enabled": bool(client.access_token or (client.refresh_token and client.client_id)),
                "actual_enabled": client.enabled
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Credential debug error: {str(e)}")
        return {"error": str(e)}

@app.post("/debug/test-token-refresh")
async def test_token_refresh():
    """Test Google Calendar token refresh manually"""
    try:
        from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
        
        client = DirectGoogleCalendarClient()
        
        if not client.enabled:
            return {"error": "Client not enabled - missing credentials"}
        
        # Force a token validity check
        await client._ensure_valid_token()
        
        return {
            "success": True,
            "client_enabled_after_refresh": client.enabled,
            "has_access_token_after_refresh": bool(client.access_token),
            "message": "Token refresh test completed - check logs for details"
        }
        
    except Exception as e:
        logger.error(f"❌ Token refresh test error: {str(e)}")
        return {"error": str(e)}

@app.post("/debug/simulate-sms")
async def simulate_sms(request: Request, db: Session = Depends(get_db)):
    """Simulate SMS processing to debug the full flow"""
    try:
        data = await request.json()
        phone = data.get("phone", "+1234567890")
        message = data.get("message", "Schedule family dinner tomorrow at 7pm")
        first_name = data.get("first_name", "Debug")
        last_name = data.get("last_name", "Test")
        
        logger.info(f"🧪 SIMULATING SMS: From {phone}, Message: '{message}'")
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone)
        logger.info(f"📞 Normalized phone: {normalized_phone}")
        
        # Get team member
        team_member = get_team_member_by_phone(normalized_phone, db)
        if not team_member:
            return {
                "error": "No team member found for this phone",
                "suggestion": "Add family member first with /admin/add-family-member"
            }
        
        logger.info(f"👤 Found team member: {team_member.name}")
        
        # Get conversation
        conversation = get_or_create_conversation(normalized_phone, db)
        logger.info(f"💬 Conversation ID: {conversation.id}")
        
        # Process the command
        logger.info(f"🤖 Processing command with command processor...")
        response = await command_processor.process_command_with_llm(
            message_text=message,
            team_member=team_member,
            conversation=conversation,
            db=db
        )
        
        logger.info(f"✅ Command processing complete. Response: {response}")
        
        return {
            "success": True,
            "phone": normalized_phone,
            "team_member": team_member.name,
            "message_sent": message,
            "response_received": response,
            "debug_info": {
                "team_id": str(team_member.team_id),
                "conversation_id": str(conversation.id),
                "command_processor_type": type(command_processor).__name__,
                "calendar_client_type": type(calendar_client).__name__
            }
        }
        
    except Exception as e:
        logger.error(f"❌ SMS simulation error: {str(e)}", exc_info=True)
        return {"error": str(e)}

@app.get("/debug/sms-flow-status")
async def debug_sms_flow_status(db: Session = Depends(get_db)):
    """Check the status of the SMS processing flow"""
    try:
        # Check family members
        from database.models import Team, TeamMember
        team = db.query(Team).filter(Team.name == "Family").first()
        
        if not team:
            return {
                "error": "No Family team found",
                "suggestion": "Add family members first"
            }
        
        members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        
        # Check member details
        member_info = []
        members_with_email = 0
        for member in members:
            has_email = bool(member.email)
            if has_email:
                members_with_email += 1
            
            member_info.append({
                "name": member.name,
                "phone": member.phone,
                "has_email": has_email,
                "email": member.email if has_email else "❌ Missing"
            })
        
        # Check command processor configuration
        processor_info = {
            "type": type(command_processor).__name__,
            "llm_enabled": getattr(command_processor, 'llm_enabled', False),
            "calendar_client_type": type(calendar_client).__name__,
            "calendar_enabled": getattr(calendar_client, 'enabled', False)
        }
        
        # Check environment variables
        env_status = {
            "use_direct_google_calendar": os.getenv("USE_DIRECT_GOOGLE_CALENDAR"),
            "use_real_mcp_calendar": os.getenv("USE_REAL_MCP_CALENDAR"),
            "anthropic_api_key_present": bool(os.getenv("ANTHROPIC_API_KEY")),
            "surge_credentials_present": bool(os.getenv("SURGE_SMS_API_KEY") and os.getenv("SURGE_ACCOUNT_ID"))
        }
        
        return {
            "team_info": {
                "team_name": team.name,
                "total_members": len(members),
                "members_with_email": members_with_email,
                "members": member_info
            },
            "processor_info": processor_info,
            "environment_status": env_status,
            "diagnosis": {
                "can_create_calendar_events": processor_info["calendar_enabled"],
                "can_send_invites": members_with_email > 0,
                "llm_processing_available": processor_info["llm_enabled"],
                "sms_integration_configured": env_status["surge_credentials_present"]
            },
            "recommendations": [
                "Add email addresses to family members" if members_with_email == 0 else None,
                "Set ANTHROPIC_API_KEY for smart LLM processing" if not env_status["anthropic_api_key_present"] else None,
                "Check SMS webhook configuration" if not env_status["surge_credentials_present"] else None
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ SMS flow status error: {str(e)}")
        return {"error": str(e)}

@app.post("/debug/test-datetime-parsing")
async def test_datetime_parsing(request: Request):
    """Test datetime parsing with various inputs"""
    try:
        data = await request.json()
        test_strings = data.get("test_strings", [
            "tomorrow at 2pm",
            "today at 3:30pm", 
            "friday morning",
            "this weekend",
            "monday 9am",
            "next tuesday 2:30pm",
            "tomorrow 14:00",
            "saturday evening"
        ])
        
        # Import the command processor to access the parsing method
        from llm_integration.enhanced_command_processor import LLMCommandProcessor
        
        # Create a temporary instance to test parsing
        temp_processor = LLMCommandProcessor(None, None, None, None)
        
        results = []
        for test_str in test_strings:
            try:
                parsed_dt = temp_processor._parse_datetime(test_str)
                if parsed_dt:
                    results.append({
                        "input": test_str,
                        "parsed": parsed_dt.isoformat(),
                        "formatted": parsed_dt.strftime("%A, %B %d, %Y at %I:%M %p"),
                        "success": True
                    })
                else:
                    results.append({
                        "input": test_str,
                        "error": "Failed to parse",
                        "success": False
                    })
            except Exception as e:
                results.append({
                    "input": test_str,
                    "error": str(e),
                    "success": False
                })
        
        return {
            "datetime_parsing_test": results,
            "current_time": datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
            "timezone": "America/New_York (assumed)"
        }
        
    except Exception as e:
        logger.error(f"❌ Datetime parsing test error: {str(e)}")
        return {"error": str(e)}

@app.post("/debug/timezone-test")
async def test_timezone_calculation(request: Request):
    """Debug timezone calculation for calendar events"""
    try:
        data = await request.json()
        hours_from_now = data.get("hours_from_now", 2)
        
        # Get current times in different formats
        from datetime import datetime, timedelta, timezone
        
        # Server time (probably UTC on Railway)
        server_now = datetime.now()
        server_target = server_now + timedelta(hours=hours_from_now)
        
        # UTC time
        utc_now = datetime.utcnow()
        utc_target = utc_now + timedelta(hours=hours_from_now)
        
        # Eastern time (what user probably expects) - manually calculate offset
        # EDT is UTC-4, EST is UTC-5
        eastern_offset = -4  # Assuming EDT (summer time)
        eastern_now = utc_now + timedelta(hours=eastern_offset)
        eastern_target = eastern_now + timedelta(hours=hours_from_now)
        
        return {
            "hours_requested": hours_from_now,
            "server_time": {
                "now": server_now.strftime("%Y-%m-%d %H:%M:%S"),
                "target": server_target.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "Server Local (probably UTC)"
            },
            "utc_time": {
                "now": utc_now.strftime("%Y-%m-%d %H:%M:%S"),
                "target": utc_target.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "UTC"
            },
            "eastern_time": {
                "now": eastern_now.strftime("%Y-%m-%d %H:%M:%S EDT"),
                "target": eastern_target.strftime("%Y-%m-%d %H:%M:%S EDT"),
                "timezone": "America/New_York (EDT)"
            },
            "diagnosis": {
                "server_probably_utc": server_now.hour == utc_now.hour,
                "current_eastern_offset": "UTC-4 (EDT)",
                "google_calendar_expects": "America/New_York timezone",
                "hours_difference": (server_now.hour - eastern_now.hour) % 24
            }
        }
        
    except Exception as e:
        return {"error": str(e)}
@app.post("/debug/test-calendar-invites")
async def test_calendar_invites(request: Request, db: Session = Depends(get_db)):
    """Test calendar invite functionality specifically"""
    try:
        data = await request.json()
        phone = data.get("phone", "+1234567890")
        test_emails = data.get("test_emails", [])  # Optional: override with test emails
        
        # Get team member
        normalized_phone = normalize_phone_number(phone)
        team_member = get_team_member_by_phone(normalized_phone, db)
        
        if not team_member:
            return {
                "error": "No team member found",
                "suggestion": "Add this phone number as a family member first"
            }
        
        # Get all family members
        from database.models import Team, TeamMember
        team = db.query(Team).filter(Team.id == team_member.team_id).first()
        all_members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
        
        # Check email status
        members_info = []
        attendee_emails = []
        
        for member in all_members:
            has_email = bool(member.email)
            members_info.append({
                "name": member.name,
                "phone": member.phone,
                "email": member.email,
                "has_email": has_email,
                "is_creator": member.phone == team_member.phone
            })
            
            # Add to attendees if has email and not the creator
            if has_email and member.phone != team_member.phone:
                attendee_emails.append(member.email)
        
        # Use test emails if provided
        if test_emails:
            attendee_emails = test_emails
            logger.info(f"🧪 Using test emails instead: {attendee_emails}")
        
        # Create test calendar event with invites
        if attendee_emails:
            from google_integrations.direct_google_calendar import DirectGoogleCalendarClient
            
            calendar_client = DirectGoogleCalendarClient()
            
            if calendar_client.enabled:
                test_time = datetime.now() + timedelta(hours=2)
                
                logger.info(f"🧪 TESTING CALENDAR INVITES:")
                logger.info(f"   Event: Test Invite Debug")
                logger.info(f"   Time: {test_time}")
                logger.info(f"   Attendees: {attendee_emails}")
                
                event = await calendar_client.create_event(
                    title="Test Calendar Invite Debug",
                    start_time=test_time,
                    duration_minutes=30,
                    attendees=attendee_emails,
                    meet_link=None
                )
                
                return {
                    "test_result": "success" if event else "failed",
                    "event_created": bool(event),
                    "event_data": event,
                    "team_members": members_info,
                    "attendee_emails_used": attendee_emails,
                    "attendees_count": len(attendee_emails),
                    "calendar_client_enabled": calendar_client.enabled,
                    "recommendations": [
                        "Check Railway logs for detailed invite processing" if event else "Check Google Calendar API credentials",
                        "Verify family members have valid email addresses",
                        "Check that attendee emails are being sent to Google API"
                    ]
                }
            else:
                return {
                    "error": "Google Calendar client not enabled",
                    "team_members": members_info,
                    "attendee_emails_extracted": attendee_emails
                }
        else:
            return {
                "error": "No attendee emails found",
                "team_members": members_info,
                "issue": "Family members missing email addresses or only one person in team",
                "suggestion": "Add family members with email addresses using /admin/add-family-member"
            }
        
    except Exception as e:
        logger.error(f"❌ Calendar invite test error: {str(e)}", exc_info=True)
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))