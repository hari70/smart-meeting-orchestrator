# main.py - Debug server lifecycle
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os
import logging
import signal
import sys
from datetime import datetime
import asyncio

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Debug Server Lifecycle")

# Track server state
server_start_time = datetime.utcnow()
request_count = 0

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 STARTUP EVENT TRIGGERED")
    logger.info(f"📊 Process ID: {os.getpid()}")
    logger.info(f"🐍 Python version: {sys.version}")
    logger.info(f"🌐 PORT env var: {os.getenv('PORT', 'NOT_SET')}")
    logger.info("✅ STARTUP COMPLETE - SERVER SHOULD STAY RUNNING")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 SHUTDOWN EVENT TRIGGERED")
    logger.info(f"⏱️ Server ran for: {datetime.utcnow() - server_start_time}")
    logger.info(f"📊 Total requests handled: {request_count}")

@app.get("/health")
async def health():
    global request_count
    request_count += 1
    
    uptime = datetime.utcnow() - server_start_time
    logger.info(f"🏥 Health check #{request_count} - Uptime: {uptime}")
    
    return {
        "status": "healthy",
        "uptime_seconds": uptime.total_seconds(),
        "process_id": os.getpid(),
        "request_count": request_count,
        "port": os.getenv("PORT", "8000")
    }

@app.get("/debug")
async def debug():
    global request_count
    request_count += 1
    
    return {
        "server_running": True,
        "uptime": (datetime.utcnow() - server_start_time).total_seconds(),
        "process_id": os.getpid(),
        "port": os.getenv("PORT", "8000"),
        "railway_env": {
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
            "RAILWAY_SERVICE_NAME": os.getenv("RAILWAY_SERVICE_NAME"),
            "RAILWAY_PROJECT_NAME": os.getenv("RAILWAY_PROJECT_NAME")
        }
    }

@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    global request_count
    request_count += 1
    
    logger.info(f"🎯 WEBHOOK RECEIVED - Request #{request_count}")
    
    try:
        payload = await request.json()
        logger.info(f"📱 Webhook payload: {payload}")
        
        return JSONResponse({
            "status": "webhook_received",
            "request_number": request_count,
            "server_uptime": (datetime.utcnow() - server_start_time).total_seconds()
        })
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Signal handlers to detect why server might exit
def signal_handler(signum, frame):
    logger.info(f"🚨 SIGNAL RECEIVED: {signum}")
    logger.info(f"⏱️ Server uptime before signal: {datetime.utcnow() - server_start_time}")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    logger.info("🔥 STARTING UVICORN SERVER")
    
    import uvicorn
    
    # Get port from Railway
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 Binding to port: {port}")
    
    # Run with explicit configuration
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=True
    )
    
    logger.info("🛑 UVICORN.RUN COMPLETED - THIS SHOULD NOT HAPPEN")
