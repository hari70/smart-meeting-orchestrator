"""
Simple SMS → LLM → MCP Google Calendar System
Clean FastAPI app with single SMS webhook endpoint.
"""
import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.connection import get_db, create_tables
from database.models import TeamMember, Team
from simple_sms_orchestrator import SimpleSMSOrchestrator
from mcp_integration.real_mcp_calendar_client import RealMCPCalendarClient
from sms_coordinator.surge_client import SurgeSMSClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Smart Meeting Orchestrator - Simplified",
    description="SMS frontend for MCP Google Calendar tools",
    version="2.0.0"
)

# Initialize clients with error handling
try:
    mcp_client = RealMCPCalendarClient()
    sms_client = SurgeSMSClient(
        api_key=os.getenv("SURGE_SMS_API_KEY", ""),
        account_id=os.getenv("SURGE_ACCOUNT_ID", "")
    )
    
    # Initialize the simplified orchestrator
    orchestrator = SimpleSMSOrchestrator(mcp_client, sms_client)
    logger.info("✅ SimpleSMSOrchestrator initialized successfully")
    
except Exception as e:
    logger.error(f"❌ Failed to initialize orchestrator: {e}")
    # Create a minimal fallback for health checks
    class MinimalOrchestrator:
        def __init__(self):
            self.llm_enabled = False
            self.mcp_tools = []
            self.mcp_client = type('obj', (object,), {
                'mcp_enabled': False,
                'mcp_endpoint': 'not_configured'
            })()
        
        async def process_sms(self, message, phone, db):
            return "❌ Service temporarily unavailable - please try again later"
    
    orchestrator = MinimalOrchestrator()
    logger.warning("⚠️ Using minimal orchestrator for deployment")

@app.on_event("startup")
async def startup_event():
    """Initialize database"""
    create_tables()
    logger.info("🚀 Simple Smart Meeting Orchestrator started")

@app.get("/")
async def root():
    return {
        "name": "Smart Meeting Orchestrator - Simplified",
        "description": "SMS → LLM → MCP Google Calendar",
        "version": "2.0.0",
        "mcp_enabled": orchestrator.mcp_client.mcp_enabled,
        "llm_enabled": orchestrator.llm_enabled
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway deployment"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "SMS Meeting Orchestrator",
            "version": "2.0.0",
            "mcp_available": orchestrator.mcp_client.mcp_enabled,
            "llm_available": orchestrator.llm_enabled
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def _normalize_phone(phone: str) -> str:
    """Normalize phone number format"""
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone.startswith("+"):
        if phone.startswith("1"):
            phone = "+" + phone
        else:
            phone = "+1" + phone
    return phone

def _get_or_create_team_member(phone: str, first_name: str, last_name: str, db: Session) -> TeamMember:
    """Get existing team member or create new one"""
    
    # Look for existing member
    member = db.query(TeamMember).filter(TeamMember.phone == phone).first()
    if member:
        return member
    
    # Create new member
    name = f"{first_name} {last_name}".strip() or "Unknown User"
    
    # Create or get default team
    team = db.query(Team).first()
    if not team:
        team = Team(name="Default Team")
        db.add(team)
        db.commit()
        db.refresh(team)
    
    member = TeamMember(
        name=name,
        phone=phone,
        team_id=team.id
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    
    logger.info(f"👤 Created new team member: {name} ({phone})")
    return member

@app.post("/webhook/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """Single SMS webhook endpoint - SMS → LLM → MCP → Response"""
    
    try:
        # Parse incoming SMS payload
        payload = await request.json()
        logger.info(f"📱 Incoming SMS webhook: {payload}")
        
        # Handle different payload formats (Surge SMS)
        event_type = payload.get("type", payload.get("event", ""))
        if event_type not in ["message.received"]:
            logger.info(f"Ignoring non-message event: {event_type}")
            return {"status": "ignored"}
        
        # Extract message data (handle both formats)
        message_data = payload.get("data", payload.get("message", {}))
        conversation_data = message_data.get("conversation", {})
        contact_data = conversation_data.get("contact", {})
        
        # Get SMS details
        from_number = contact_data.get("phone_number", "").strip()
        message_text = message_data.get("body", "").strip()
        first_name = contact_data.get("first_name", "")
        last_name = contact_data.get("last_name", "")
        
        if not from_number or not message_text:
            logger.warning("Invalid SMS payload - missing phone or message")
            return JSONResponse(
                status_code=400, 
                content={"error": "Invalid SMS payload"}
            )
        
        # Normalize phone number
        from_number = _normalize_phone(from_number)
        
        # Get or create team member
        member = _get_or_create_team_member(from_number, first_name, last_name, db)
        
        # Process SMS through simplified orchestrator
        logger.info(f"🎯 Processing: '{message_text}' from {member.name}")
        response_text = await orchestrator.process_sms(
            message=message_text,
            user_phone=from_number,
            user_name=str(member.name),
            db=db
        )
        
        # Send SMS response
        if response_text:
            await sms_client.send_message(from_number, response_text, first_name, last_name)
            logger.info(f"📤 Sent SMS response to {member.name}")
        
        return {"status": "processed"}
        
    except Exception as e:
        logger.error(f"❌ SMS webhook error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

@app.get("/debug/status")
async def debug_status():
    """Debug endpoint to check system status"""
    return {
        "system": "Simple SMS Orchestrator",
        "components": {
            "mcp_client": {
                "type": "RealMCPCalendarClient",
                "mcp_enabled": orchestrator.mcp_client.mcp_enabled,
                "endpoint": orchestrator.mcp_client.mcp_endpoint
            },
            "llm_client": {
                "type": "Claude 3.5 Sonnet",
                "enabled": orchestrator.llm_enabled
            },
            "sms_client": {
                "type": "SurgeSMSClient", 
                "api_key_set": bool(sms_client.api_key)
            }
        },
        "available_tools": len(orchestrator.mcp_tools),
        "environment": {
            "anthropic_api_key": bool(os.getenv("ANTHROPIC_API_KEY")),
            "railway_mcp_endpoint": bool(os.getenv("RAILWAY_MCP_ENDPOINT")),
            "surge_api_key": bool(os.getenv("SURGE_SMS_API_KEY") or os.getenv("SURGE_API_KEY"))
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uuid
from contextlib import asynccontextmanager
import logging
import os

from database.connection import create_tables
# Disable old complex routers - using simplified system only
# from app.routers import all_routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("startup")

@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover
    try:
        create_tables()
        logger.info("🚀 Smart Meeting Orchestrator started (lifespan init)")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization failed: {e}. App will continue without database.")
        logger.info("🚀 Smart Meeting Orchestrator started (lifespan init - limited mode)")
    yield
    logger.info("👋 Lifespan shutdown")

app = FastAPI(
    title="Smart Meeting Orchestrator",
    description="SMS-based meeting coordination via SMS + Calendar + LLM",
    version="1.0.0",
    lifespan=lifespan,
)

def _include_routers(app: FastAPI):
    # Old complex routers disabled for simplified system
    logger.info("✅ Using simplified SMS orchestrator only - no legacy routers")
    pass


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # pragma: no cover
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={
        "error": {"type": exc.__class__.__name__, "message": str(exc)},
        "request_id": getattr(request.state, "request_id", None)
    })

_include_routers(app)

# The simplified system uses SimpleSMSOrchestrator only - no complex fallbacks needed
logger.info("✅ Using SimpleSMSOrchestrator - clean SMS → LLM → MCP pipeline")

if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

