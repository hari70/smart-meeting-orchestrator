from fastapi import APIRouter, Depends, Request
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import logging
import os

from database.connection import get_db
from database.models import Team, TeamMember, Meeting, Conversation
from app import services

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def root():
    return {"message": "Smart Meeting Orchestrator", "status": "running", "version": "1.0.0"}


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/debug-anthropic")
async def debug_anthropic():
    """PUBLIC DEBUG: Test Anthropic API key and client initialization"""
    try:
        import anthropic
        anthropic_available = True
        anthropic_version = anthropic.__version__
    except ImportError:
        anthropic_available = False
        anthropic_version = None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    api_key_present = bool(api_key)
    api_key_length = len(api_key) if api_key else 0
    api_key_prefix = api_key[:10] if api_key else None

    # Try to initialize client
    client_initialized = False
    client_error = None
    api_call_success = False
    api_call_error = None

    if anthropic_available and api_key_present:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client_initialized = True

            # Try a simple API call
            try:
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=50,
                    temperature=0.0,
                    system="You are a helpful assistant.",
                    messages=[{"role": "user", "content": "Say 'test'"}]
                )
                api_call_success = True
            except Exception as e:
                api_call_error = str(e)

        except Exception as e:
            client_error = str(e)

    return {
        "anthropic_available": anthropic_available,
        "anthropic_version": anthropic_version,
        "api_key_present": api_key_present,
        "api_key_length": api_key_length,
        "api_key_prefix": api_key_prefix,
        "client_initialized": client_initialized,
        "client_error": client_error,
        "api_call_success": api_call_success,
        "api_call_error": api_call_error
    }


@router.get("/teams")
async def list_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [{"id": str(team.id), "name": team.name} for team in teams]


@router.get("/teams/{team_id}/members")
async def list_team_members(team_id: str, db: Session = Depends(get_db)):
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    return [
        {"id": str(m.id), "name": m.name, "phone": m.phone, "is_admin": m.is_admin}
        for m in members
    ]


@router.get("/meetings")
async def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(10).all()
    return [
        {
            "id": str(meeting.id),
            "title": meeting.title,
            "scheduled_time": meeting.scheduled_time.isoformat() if getattr(meeting, "scheduled_time", None) else None,
            "google_meet_link": meeting.google_meet_link
        }
        for meeting in meetings
    ]


@router.post("/test/create-calendar-event")
async def test_create_calendar_event(request: Request):
    """Public endpoint to test Google Calendar integration."""
    try:
        data = await request.json()
        title = data.get("title", "Test Event from SMS Bot")
        hours_from_now = data.get("hours_from_now", 2)
        duration_minutes = data.get("duration_minutes", 60)
        
        # Calculate start time
        start_time = datetime.now() + timedelta(hours=hours_from_now)
        
        logger.info(f"🧪 Testing calendar event creation: {title} at {start_time}")
        
        # Create calendar event using the calendar client
        result = await services.calendar_client.create_event(
            title=title,
            start_time=start_time,
            duration_minutes=duration_minutes,
            attendees=None,
            meet_link=None
        )
        
        if result:
            is_real = result.get("source") != "mock"
            logger.info(f"✅ Calendar event test: {'REAL' if is_real else 'MOCK'} event created")
            
            return {
                "success": True,
                "message": "Calendar event created!",
                "event_details": {
                    "title": result.get("title"),
                    "start_time": result.get("start_time"),
                    "calendar_link": result.get("calendar_link"),
                    "meet_link": result.get("meet_link")
                },
                "integration_type": "real_google_api" if is_real else "mock_mode",
                "google_calendar_working": is_real,
                "setup_needed": not is_real
            }
        else:
            logger.error("❌ Calendar event creation returned None")
            return {
                "success": False,
                "message": "Failed to create calendar event",
                "integration_type": "failed",
                "google_calendar_working": False,
                "setup_needed": True
            }
            
    except Exception as e:
        logger.error(f"❌ Error in calendar test: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "integration_type": "error",
            "google_calendar_working": False,
            "setup_needed": True
        }


@router.post("/test/llm-response")
async def test_llm_response(request: Request, db: Session = Depends(get_db)):
    """Test endpoint to see what the LLM actually responds with (without sending SMS)."""
    import traceback
    
    try:
        data = await request.json()
        message = data.get("message", "schedule a meeting tomorrow at 2pm")
        phone = data.get("phone", "+12345678901")
        
        # Simulate the same flow as webhook but return the response
        conversation = db.query(Conversation).filter(Conversation.phone_number == phone).first()
        if not conversation:
            conversation = Conversation(phone_number=phone, context={}, last_activity=datetime.now())
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        
        # Get or create a test member
        member = db.query(TeamMember).filter(TeamMember.phone == phone).first()
        if not member:
            team = db.query(Team).filter(Team.name == "Family").first()
            if not team:
                team = Team(name="Family")
                db.add(team)
                db.commit()
                db.refresh(team)
            member = TeamMember(team_id=team.id, name="Test User", phone=phone, is_admin=True)
            db.add(member)
            db.commit()
            db.refresh(member)
        
        # Process with LLM and return the actual response
        try:
            logger.info(f"🧠 [TEST] About to call LLM processor with message: {message}")
            logger.info(f"👤 [TEST] Team member: {member.name} (phone: {member.phone})")
            logger.info(f"🏢 [TEST] Team ID: {member.team_id}")
            
            llm_response = await services.command_processor.process_command_with_llm(
                message_text=message,
                team_member=member,
                conversation=conversation,
                db=db
            )
            
            logger.info(f"🤖 [TEST] LLM response received: {llm_response[:100]}...")
            
        except Exception as llm_error:
            logger.error(f"❌ [TEST] LLM processing exception: {llm_error}")
            logger.error(f"❌ [TEST] Exception type: {type(llm_error).__name__}")
            logger.error(f"❌ [TEST] Traceback:\n{traceback.format_exc()}")
            
            return {
                "success": False,
                "error": str(llm_error),
                "error_type": type(llm_error).__name__,
                "traceback": traceback.format_exc(),
                "llm_enabled": getattr(services.command_processor, 'llm_enabled', False)
            }
        
        return {
            "success": True,
            "input_message": message,
            "llm_response": llm_response,
            "llm_enabled": getattr(services.command_processor, 'llm_enabled', False),
            "response_length": len(llm_response) if llm_response else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Error testing LLM response: {e}")
        logger.error(f"❌ Traceback:\n{traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "llm_enabled": getattr(services.command_processor, 'llm_enabled', False)
        }


@router.get("/test/environment-check")
async def test_environment_check():
    """Public endpoint to check critical environment variables (masked for security)."""
    import os
    
    def mask_key(key, show_chars=8):
        if not key:
            return "NOT_SET"
        return key[:show_chars] + "***" + key[-4:] if len(key) > show_chars else "SET_BUT_SHORT"
    
    return {
        "environment_status": {
            "ANTHROPIC_API_KEY": mask_key(os.getenv("ANTHROPIC_API_KEY")),
            "SURGE_SMS_API_KEY": mask_key(os.getenv("SURGE_SMS_API_KEY")),
            "SURGE_ACCOUNT_ID": mask_key(os.getenv("SURGE_ACCOUNT_ID")),
            "GOOGLE_CALENDAR_ACCESS_TOKEN": mask_key(os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN")),
            "GOOGLE_CALENDAR_REFRESH_TOKEN": mask_key(os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN")),
            "GOOGLE_CALENDAR_CLIENT_ID": mask_key(os.getenv("GOOGLE_CALENDAR_CLIENT_ID")),
            "GOOGLE_CALENDAR_CLIENT_SECRET": mask_key(os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")),
            "DATABASE_URL": "SET" if os.getenv("DATABASE_URL") else "NOT_SET"
        },
        "note": "This shows masked environment variables to help debug integration issues"
    }


@router.post("/test/llm-tools-debug")
async def test_llm_tools_debug(request: Request):
    """Test Claude tool calling specifically to isolate the issue."""
    import traceback
    import os
    
    try:
        data = await request.json()
        message = data.get("message", "Schedule a meeting tomorrow at 2pm")
        
        # Import and setup
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        
        # Define a simple tool for testing
        test_tools = [
            {
                "name": "test_tool",
                "description": "A simple test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Test message"}
                    },
                    "required": ["message"]
                }
            }
        ]
        
        # Test with tools
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": message}],
                tools=test_tools
            )
            
            result = {
                "success": True,
                "tool_calling_works": True,
                "response_blocks": len(response.content),
                "content_types": [type(block).__name__ for block in response.content],
                "has_tool_use": any(hasattr(block, 'name') for block in response.content),
                "response_preview": str(response.content[0])[:200] if response.content else "No content"
            }
            
            return result
            
        except Exception as tool_error:
            return {
                "success": False,
                "tool_calling_works": False,
                "error_in_tool_call": str(tool_error),
                "error_type": type(tool_error).__name__,
                "traceback": traceback.format_exc()
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.post("/test/llm-debug")
async def test_llm_debug(request: Request):
    """Detailed LLM debugging endpoint to catch specific errors."""
    import traceback
    import os
    
    try:
        data = await request.json()
        message = data.get("message", "test message")
        
        # Test Anthropic SDK step by step
        debug_info = {
            "step_1_env_var": bool(os.getenv("ANTHROPIC_API_KEY")),
            "step_2_import": False,
            "step_3_client_init": False,
            "step_4_api_call": False,
            "error_details": None,
            "anthropic_version": None
        }
        
        # Step 1: Check environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        debug_info["api_key_format"] = f"{api_key[:15]}...{api_key[-4:]}" if api_key else None
        
        # Step 2: Test import
        try:
            import anthropic
            debug_info["step_2_import"] = True
            debug_info["anthropic_version"] = getattr(anthropic, '__version__', 'unknown')
        except Exception as e:
            debug_info["error_details"] = f"Import error: {str(e)}"
            return debug_info
        
        # Step 3: Test client initialization
        try:
            client = anthropic.Anthropic(api_key=api_key)
            debug_info["step_3_client_init"] = True
        except Exception as e:
            debug_info["error_details"] = f"Client init error: {str(e)}"
            return debug_info
        
        # Step 4: Test API call
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=50,
                messages=[{"role": "user", "content": message}]
            )
            debug_info["step_4_api_call"] = True
            debug_info["api_response"] = response.content[0].text if response.content else "Empty response"
        except Exception as e:
            debug_info["error_details"] = f"API call error: {str(e)}"
            debug_info["error_type"] = type(e).__name__
            debug_info["traceback"] = traceback.format_exc()
            return debug_info
        
        debug_info["success"] = True
        return debug_info
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.get("/test/calendar-status")
async def test_calendar_status():
    """Public endpoint to check Google Calendar integration status."""
    try:
        c = services.calendar_client
        
        # Check what credentials are available
        has_access_token = bool(getattr(c, 'access_token', None))
        has_refresh_token = bool(getattr(c, 'refresh_token', None))
        has_client_creds = bool(getattr(c, 'client_id', None)) and bool(getattr(c, 'client_secret', None))
        
        return {
            "calendar_integration_enabled": getattr(c, 'enabled', False),
            "calendar_mode": "real_google_api" if getattr(c, 'enabled', False) else "mock_mode",
            "credentials_status": {
                "has_access_token": has_access_token,
                "has_refresh_token": has_refresh_token,
                "has_oauth_credentials": has_client_creds,
                "recommended_setup": "refresh_token" if not has_refresh_token else "working"
            },
            "setup_guide": "See GOOGLE_CALENDAR_SETUP.md for detailed setup instructions",
            "test_endpoint": "/test/create-calendar-event"
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking calendar status: {e}")
        return {
            "calendar_integration_enabled": False,
            "calendar_mode": "error",
            "error": str(e)
        }
