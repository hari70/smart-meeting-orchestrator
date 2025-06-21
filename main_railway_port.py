# main.py - Force Railway PORT compliance
from fastapi import FastAPI
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    logger.info("🏥 Health check received")
    return {"status": "healthy", "port": os.getenv("PORT", "not_set")}

@app.get("/")
async def root():
    logger.info("🏠 Root endpoint hit")
    return {"message": "Railway app working", "port": os.getenv("PORT", "not_set")}

if __name__ == "__main__":
    import uvicorn
    
    # Force use Railway's PORT
    railway_port = os.getenv("PORT")
    if railway_port:
        port = int(railway_port)
        logger.info(f"🚂 Using Railway PORT: {port}")
    else:
        port = 8000
        logger.info(f"⚠️ No Railway PORT, using default: {port}")
    
    logger.info(f"🌐 Starting server on 0.0.0.0:{port}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
