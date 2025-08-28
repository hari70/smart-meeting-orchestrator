"""
Robust SMS → LLM → MCP Google Calendar System
Clean FastAPI app with defensive initialization and comprehensive error handling.
"""
import os
import logging
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI first - critical for Railway health checks
app = FastAPI(
    title="Smart Meeting Orchestrator",
    description="SMS frontend for MCP Google Calendar tools",
    version="2.1.0"
)

# Global service instances
orchestrator: Optional[object] = None
db_available: bool = False

class SMSPayload(BaseModel):
    """SMS webhook payload structure"""
    type: str
    data: dict

# CRITICAL: Health endpoints first - no dependencies
@app.get("/health")
async def health_check():
    """Railway deployment health check - always returns ok"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    """Root endpoint with service status"""
    return {
        "name": "Smart Meeting Orchestrator",
        "version": "2.1.0",
        "status": "running",
        "orchestrator_ready": orchestrator is not None,
        "database_available": db_available
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return "pong"

def initialize_services():
    """Initialize all services with comprehensive error handling"""
    global orchestrator, db_available
    
    logger.info("🚀 Initializing services...")
    
    # Try to initialize database
    try:
        from database.connection import create_tables
        create_tables()
        db_available = True
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"⚠️ Database unavailable: {e}")
        db_available = False
    
    # Try to initialize orchestrator
    try:
        from simple_sms_orchestrator import SimpleSMSOrchestrator
        from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
        from sms_coordinator.surge_client import SurgeSMSClient
        
        # Initialize MCP client
        mcp_client = RealMCPCalendarClient()
        
        # Initialize SMS client
        sms_client = SurgeSMSClient(
            api_key=os.getenv("SURGE_SMS_API_KEY", ""),
            account_id=os.getenv("SURGE_ACCOUNT_ID", "")
        )
        
        # Initialize orchestrator
        orchestrator = SimpleSMSOrchestrator(mcp_client, sms_client)
        logger.info("✅ SimpleSMSOrchestrator initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize orchestrator: {e}")
        
        # Create minimal fallback orchestrator
        class FallbackOrchestrator:
            def __init__(self):
                self.mcp_enabled = False
                self.llm_enabled = False
                
            async def process_sms(self, message: str, user_phone: str, user_name: str, db=None) -> str:
                """Fallback SMS processing"""
                logger.info(f"📱 Fallback processing SMS from {user_name}: {message}")
                return f"🤖 Service is initializing. Your message '{message[:50]}...' has been received. Please try again in a moment."
        
        orchestrator = FallbackOrchestrator()
        logger.info("⚠️ Using fallback orchestrator")

def get_db_session():
    """Get database session with error handling"""
    if not db_available:
        return None
    
    try:
        from database.connection import get_db
        return next(get_db())
    except Exception as e:
        logger.error(f"Database session error: {e}")
        return None

def normalize_phone(phone: str) -> str:
    """Normalize phone number format"""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        if phone.startswith("1"):
            phone = "+" + phone
        else:
            phone = "+1" + phone
    return phone

def get_or_create_user(phone: str, first_name: str, last_name: str, db) -> str:
    """Get or create user with error handling"""
    if not db:
        return f"{first_name} {last_name}".strip() or "User"
    
    try:
        from database.models import TeamMember, Team
        
        # Look for existing member
        member = db.query(TeamMember).filter(TeamMember.phone == phone).first()
        if member:
            return str(member.name)
        
        # Create new member
        name = f"{first_name} {last_name}".strip() or "Unknown User"
        
        # Get or create default team
        team = db.query(Team).first()
        if not team:
            team = Team(name="Default Team")
            db.add(team)
            db.commit()
            db.refresh(team)
        
        member = TeamMember(name=name, phone=phone, team_id=team.id)
        db.add(member)
        db.commit()
        
        logger.info(f"👤 Created user: {name}")
        return name
        
    except Exception as e:
        logger.error(f"User creation error: {e}")
        return f"{first_name} {last_name}".strip() or "User"

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """SMS webhook endpoint with robust error handling"""
    
    try:
        # Parse payload
        payload = await request.json()
        logger.info(f"📱 SMS webhook: {payload}")
        
        # Check event type
        event_type = payload.get("type", "")
        if event_type != "message.received":
            return {"status": "ignored", "event": event_type}
        
        # Extract message data
        message_data = payload.get("data", {})
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        
        # Get SMS details
        from_number = normalize_phone(contact_data.get("phone_number", ""))
        message_text = message_data.get("body", "").strip()
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        
        if not from_number or not message_text:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing phone or message"}
            )
        
        # Get database session
        db = get_db_session()
        
        # Get or create user
        user_name = get_or_create_user(from_number, first_name, last_name, db)
        
        # Check if orchestrator is available
        if not orchestrator:
            response_text = "🤖 Service is starting up. Please try again in a moment."
        else:
            # Process SMS
            logger.info(f"🎯 Processing '{message_text}' from {user_name}")
            response_text = await orchestrator.process_sms(
                message=message_text,
                user_phone=from_number,
                user_name=user_name,
                db=db
            )
        
        # Send response (if SMS client available)
        try:
            if hasattr(orchestrator, 'sms_client') and orchestrator.sms_client:
                await orchestrator.sms_client.send_message(
                    from_number, response_text, first_name, last_name
                )
                logger.info(f"📤 SMS sent to {user_name}")
        except Exception as e:
            logger.error(f"SMS send error: {e}")
        
        return {"status": "processed", "user": user_name}
        
    except Exception as e:
        logger.error(f"❌ SMS webhook error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Processing failed"}
        )

@app.get("/debug/status")
async def debug_status():
    """Debug status endpoint"""
    status = {
        "system": "Smart Meeting Orchestrator",
        "orchestrator_available": orchestrator is not None,
        "database_available": db_available,
        "environment": {
            "anthropic_api_key": bool(os.getenv("ANTHROPIC_API_KEY")),
            "surge_api_key": bool(os.getenv("SURGE_SMS_API_KEY")),
            "mcp_endpoint": bool(os.getenv("RAILWAY_MCP_ENDPOINT"))
        }
    }
    
    if orchestrator:
        status.update({
            "mcp_enabled": getattr(orchestrator, 'mcp_enabled', False),
            "llm_enabled": getattr(orchestrator, 'llm_enabled', False)
        })
    
    return status

# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    """Startup initialization"""
    initialize_services()
    logger.info("🚀 Smart Meeting Orchestrator ready")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main_robust:app", host="0.0.0.0", port=port, reload=True)
