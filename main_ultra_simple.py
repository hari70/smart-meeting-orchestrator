# main.py - Ultra-simple webhook (eliminate 502 causes)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    logger.info("🏥 Health check")
    return {"status": "healthy"}

@app.post("/webhook/sms")
async def webhook(request: Request):
    logger.info("🎯 WEBHOOK HIT!")
    
    try:
        # Simplest possible response
        logger.info("📤 Sending simple response")
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {"error": "failed"}

@app.get("/test")
async def test():
    logger.info("🧪 Test endpoint hit")
    return {"test": "working"}

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting server")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
