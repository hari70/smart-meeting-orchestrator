# main.py - Clean SMS → Claude → MCP → Response
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import json
import logging
import requests
import anthropic
from datetime import datetime, timedelta
import re

# Database imports
from database.connection import get_db, create_tables
from database.models import Team, TeamMember, Meeting

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Smart Meeting Orchestrator", version="2.0-clean")

# Initialize Claude client
try:
    claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    claude_available = True
    logger.info("Claude API initialized")
except:
    claude_client = None
    claude_available = False
    logger.warning("Claude API not available")

@app.on_event("startup")
async def startup_event():
    create_tables()
    logger.info("Clean SMS Orchestrator started")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "claude_available": claude_available}

@app.post("/webhook/sms")
async def sms_webhook(request: Request, db: Session = Depends(get_db)):
    """SMS → Claude → MCP → Response"""
    try:
        # 1. Parse SMS webhook
        payload = await request.json()
        logger.info(f"SMS received: {payload}")
        
        if payload.get("type") != "message.received":
            return JSONResponse({"status": "ignored"})
        
        # Extract SMS data
        data = payload.get("data", {})
        contact = data.get("conversation", {}).get("contact", {})
        
        phone = contact.get("phone_number", "").strip()
        message = data.get("body", "").strip()
        first_name = contact.get("first_name", "")
        last_name = contact.get("last_name", "")
        
        if not phone or not message:
            return JSONResponse({"error": "Invalid SMS"}, status_code=400)
        
        phone = normalize_phone(phone)
        logger.info(f"Processing: {phone} → {message}")
        
        # 2. Get or create user
        user = get_or_create_user(phone, first_name, last_name, db)
        
        # 3. Send to Claude for processing
        response_text = await process_with_claude(message, user, db)
        
        # 4. Send SMS response
        if response_text:
            await send_sms(phone, response_text, first_name, last_name)
            logger.info(f"SMS sent: {phone} ← {response_text[:50]}...")
        
        return JSONResponse({"status": "processed"})
        
    except Exception as e:
        logger.error(f"SMS processing error: {e}")
        return JSONResponse({"error": "Processing failed"}, status_code=500)

async def process_with_claude(message: str, user, db: Session) -> str:
    """Send message to Claude, get JSON action, execute it"""
    
    if not claude_available:
        return "SMS system working! Claude AI processing will be available soon."
    
    try:
        # Claude prompt for clean JSON response
        prompt = f"""You are a smart meeting assistant. Convert this SMS into actionable JSON.

SMS: "{message}"
User: {user.name}

Respond with ONLY a JSON object:

{{
  "action": "schedule_meeting" | "list_meetings" | "help",
  "meeting_title": "string (if scheduling)",
  "participants": ["list of names"],
  "date": "today|tomorrow|weekend|YYYY-MM-DD",
  "time": "3pm|15:00|etc (if specified)",
  "response": "what to tell the user"
}}

Examples:
- "Schedule meeting with John at 3pm today" → {{"action": "schedule_meeting", "meeting_title": "Meeting with John", "participants": ["John"], "date": "today", "time": "3pm", "response": "Scheduling meeting with John for today at 3pm"}}
- "What meetings do I have?" → {{"action": "list_meetings", "response": "Here are your upcoming meetings"}}
- "Hello" → {{"action": "help", "response": "I can help you schedule meetings! Try: 'Schedule meeting with John tomorrow'"}}"""

        # Call Claude API
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse Claude's JSON response
        claude_text = response.content[0].text.strip()
        logger.info(f"Claude response: {claude_text}")
        
        # Extract JSON from response
        json_start = claude_text.find('{')
        json_end = claude_text.rfind('}') + 1
        json_str = claude_text[json_start:json_end]
        
        action_data = json.loads(json_str)
        logger.info(f"Parsed action: {action_data}")
        
        # Execute the action
        return await execute_action(action_data, user, db)
        
    except Exception as e:
        logger.error(f"Claude processing error: {e}")
        return "I received your message! Let me help you schedule meetings. Try: 'Schedule meeting with John tomorrow'"

async def execute_action(action_data: dict, user, db: Session) -> str:
    """Execute the action from Claude's JSON response"""
    
    action = action_data.get("action", "help")
    
    if action == "schedule_meeting":
        return await schedule_meeting(action_data, user, db)
    elif action == "list_meetings":
        return await list_meetings(user, db)
    else:
        return action_data.get("response", "I can help you schedule meetings! Try: 'Schedule meeting with John tomorrow'")

async def schedule_meeting(action_data: dict, user, db: Session) -> str:
    """Schedule a meeting based on Claude's parsed data"""
    try:
        title = action_data.get("meeting_title", "Meeting")
        date_str = action_data.get("date", "today")
        time_str = action_data.get("time", "")
        
        # Calculate meeting time
        meeting_time = parse_meeting_time(date_str, time_str)
        
        # Create meeting in database
        meeting = Meeting(
            team_id=user.team_id,
            title=title,
            scheduled_time=meeting_time,
            created_by_phone=user.phone,
            description=f"Scheduled via SMS: {action_data}"
        )
        
        db.add(meeting)
        db.commit()
        
        # Format response
        time_str = meeting_time.strftime("%A, %B %d at %I:%M %p")
        return f"""✅ Meeting scheduled!

📅 {title}
🕐 {time_str}

Meeting saved to your calendar!"""
        
    except Exception as e:
        logger.error(f"Meeting scheduling error: {e}")
        return "Meeting request received! I'll help you schedule it."

async def list_meetings(user, db: Session) -> str:
    """List upcoming meetings"""
    try:
        meetings = db.query(Meeting).filter(
            Meeting.team_id == user.team_id,
            Meeting.scheduled_time > datetime.utcnow()
        ).order_by(Meeting.scheduled_time).limit(5).all()
        
        if not meetings:
            return "No upcoming meetings. Try: 'Schedule meeting with John tomorrow'"
        
        response = "📅 Your upcoming meetings:\n\n"
        for i, meeting in enumerate(meetings, 1):
            time_str = meeting.scheduled_time.strftime("%a %m/%d at %I:%M %p")
            response += f"{i}. {meeting.title}\n   {time_str}\n\n"
        
        return response.strip()
        
    except Exception as e:
        logger.error(f"List meetings error: {e}")
        return "I can show you your meetings. Try asking again!"

def parse_meeting_time(date_str: str, time_str: str) -> datetime:
    """Parse date and time strings into datetime"""
    now = datetime.utcnow()
    
    # Parse date
    if date_str == "today":
        target_date = now.date()
    elif date_str == "tomorrow":
        target_date = (now + timedelta(days=1)).date()
    elif date_str == "weekend":
        # Next Saturday
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        target_date = (now + timedelta(days=days_until_saturday)).date()
    else:
        target_date = (now + timedelta(days=1)).date()  # Default tomorrow
    
    # Parse time
    hour = 15  # Default 3 PM
    minute = 0
    
    if time_str:
        import re
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str.lower())
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            am_pm = time_match.group(3)
            
            if am_pm == "pm" and hour != 12:
                hour += 12
            elif am_pm == "am" and hour == 12:
                hour = 0
    
    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))

def get_or_create_user(phone: str, first_name: str, last_name: str, db: Session):
    """Get or create user"""
    user = db.query(TeamMember).filter(TeamMember.phone == phone).first()
    
    if not user:
        # Create team if needed
        team = db.query(Team).filter(Team.name == "Family").first()
        if not team:
            team = Team(name="Family")
            db.add(team)
            db.commit()
            db.refresh(team)
        
        # Create user
        name = f"{first_name} {last_name}".strip() or "SMS User"
        user = TeamMember(team_id=team.id, name=name, phone=phone)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"Created user: {name} ({phone})")
    
    return user

async def send_sms(phone: str, message: str, first_name: str, last_name: str) -> bool:
    """Send SMS via Surge API"""
    try:
        api_key = os.getenv("SURGE_SMS_API_KEY")
        account_id = os.getenv("SURGE_ACCOUNT_ID")
        
        if not api_key or not account_id:
            logger.warning("SMS credentials not configured")
            return False
        
        url = f"https://api.surge.app/accounts/{account_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "body": message,
            "conversation": {
                "contact": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone_number": phone
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.status_code in [200, 201]
        
    except Exception as e:
        logger.error(f"SMS sending error: {e}")
        return False

def normalize_phone(phone: str) -> str:
    """Normalize phone number"""
    cleaned = re.sub(r'[^\d+]', '', phone)
    if not cleaned.startswith('+'):
        if cleaned.startswith('1') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif len(cleaned) == 10:
            cleaned = '+1' + cleaned
        else:
            cleaned = '+' + cleaned
    return cleaned

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
