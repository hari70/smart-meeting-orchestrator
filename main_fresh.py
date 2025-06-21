# main.py - Fresh Railway deployment - minimal working version
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SMS Webhook - Fresh Deploy")

@app.get("/")
async def root():
    return {
        "status": "working", 
        "message": "Fresh Railway deployment successful",
        "port": os.getenv("PORT", "8000")
    }

@app.get("/health")
async def health():
    logger.info("Health check - Fresh deployment")
    return {"status": "healthy"}

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    try:
        payload = await request.json()
        logger.info(f"✅ SMS webhook received: {payload}")
        
        # Extract basic SMS info
        if payload.get("type") != "message.received":
            return JSONResponse({"status": "ignored"})
        
        data = payload.get("data", {})
        contact = data.get("conversation", {}).get("contact", {})
        
        phone = contact.get("phone_number", "")
        message = data.get("body", "")
        first_name = contact.get("first_name", "")
        
        logger.info(f"📱 SMS from {phone} ({first_name}): {message}")
        
        # Simple response - we can add SMS sending later
        response_msg = f"✅ Webhook working! Received: '{message}'"
        logger.info(f"📤 Would send SMS: {response_msg}")
        
        return JSONResponse({
            "status": "success",
            "message_received": message,
            "from": phone,
            "response": response_msg
        })
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    
    # Use Railway's assigned PORT
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting fresh deployment on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
