# main.py - Bulletproof minimal SMS webhook
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="SMS Webhook Test", version="minimal")

@app.get("/")
async def root():
    return {"status": "SMS webhook working", "time": datetime.utcnow().isoformat()}

@app.get("/health")
async def health():
    return {"status": "healthy", "time": datetime.utcnow().isoformat()}

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """Absolute minimal SMS webhook - just log and respond"""
    try:
        # Parse the webhook
        payload = await request.json()
        logger.info(f"✅ SMS webhook received: {payload}")
        
        # Check if it's a message
        if payload.get("type") != "message.received":
            logger.info("Not a message, ignoring")
            return JSONResponse({"status": "ignored"})
        
        # Extract basic info
        data = payload.get("data", {})
        contact = data.get("conversation", {}).get("contact", {})
        
        phone = contact.get("phone_number", "")
        message = data.get("body", "")
        first_name = contact.get("first_name", "")
        
        logger.info(f"📱 SMS from {phone} ({first_name}): {message}")
        
        # Send a simple response
        if phone and message:
            response_msg = f"✅ SMS received! You said: '{message}' - Webhook is working!"
            success = await send_simple_sms(phone, response_msg, first_name)
            logger.info(f"📤 SMS response sent: {success}")
        
        return JSONResponse({"status": "processed", "webhook_working": True})
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def send_simple_sms(phone: str, message: str, first_name: str = "User") -> bool:
    """Send SMS - absolute minimal implementation"""
    try:
        api_key = os.getenv("SURGE_SMS_API_KEY")
        account_id = os.getenv("SURGE_ACCOUNT_ID")
        
        if not api_key or not account_id:
            logger.warning("⚠️ SMS credentials missing")
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
                    "phone_number": phone
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ SMS sent successfully to {phone}")
            return True
        else:
            logger.error(f"❌ SMS failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"💥 SMS error: {str(e)}")
        return False

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify app is running"""
    return {
        "app_status": "running",
        "surge_api_key_present": bool(os.getenv("SURGE_SMS_API_KEY")),
        "surge_account_id_present": bool(os.getenv("SURGE_ACCOUNT_ID")),
        "time": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
