# main.py - Iteration 1: Pure webhook test (no database, no claude)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SMS Webhook Test - Iteration 1")

@app.get("/health")
async def health():
    return {"status": "healthy", "iteration": 1, "features": ["webhook_only"]}

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """Iteration 1: Just prove webhook delivery works"""
    try:
        payload = await request.json()
        logger.info(f"🎯 WEBHOOK RECEIVED: {payload}")
        
        # Extract SMS basics
        if payload.get("type") != "message.received":
            return JSONResponse({"status": "ignored"})
        
        data = payload.get("data", {})
        contact = data.get("conversation", {}).get("contact", {})
        
        phone = contact.get("phone_number", "")
        message = data.get("body", "")
        first_name = contact.get("first_name", "")
        
        logger.info(f"📱 SMS: {phone} → {message}")
        
        # Send immediate response
        response_msg = f"✅ Webhook working! Received: '{message}'"
        sms_sent = await send_sms_fast(phone, response_msg, first_name)
        
        logger.info(f"📤 Response sent: {sms_sent}")
        
        return JSONResponse({
            "status": "success",
            "iteration": 1,
            "webhook_received": True,
            "sms_sent": sms_sent
        })
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def send_sms_fast(phone: str, message: str, first_name: str = "User") -> bool:
    """Fast SMS sending - no delays"""
    try:
        api_key = os.getenv("SURGE_SMS_API_KEY")
        account_id = os.getenv("SURGE_ACCOUNT_ID")
        
        if not api_key or not account_id:
            logger.warning("SMS credentials missing")
            return False
        
        url = f"https://api.surge.app/accounts/{account_id}/messages"
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "body": message,
                "conversation": {
                    "contact": {
                        "first_name": first_name,
                        "phone_number": phone
                    }
                }
            },
            timeout=10
        )
        
        success = response.status_code in [200, 201]
        if not success:
            logger.error(f"SMS API error: {response.status_code} - {response.text}")
        
        return success
        
    except Exception as e:
        logger.error(f"SMS send error: {e}")
        return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
