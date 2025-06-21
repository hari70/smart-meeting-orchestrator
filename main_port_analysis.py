# main.py - Show Railway's actual PORT assignment
from fastapi import FastAPI
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    
    # Log ALL environment variables related to ports/railway
    logger.info("🔍 ENVIRONMENT VARIABLE ANALYSIS:")
    logger.info(f"   PORT: {os.getenv('PORT', 'NOT_SET')}")
    logger.info(f"   All PORT vars: {[k for k in os.environ.keys() if 'PORT' in k.upper()]}")
    logger.info(f"   All RAILWAY vars: {[k for k in os.environ.keys() if 'RAILWAY' in k.upper()]}")
    
    # Get Railway's assigned PORT
    railway_port = os.getenv("PORT")
    
    if railway_port:
        port = int(railway_port)
        logger.info(f"✅ Using Railway assigned PORT: {port}")
    else:
        port = 8000
        logger.error(f"❌ No Railway PORT assigned! Using fallback: {port}")
        logger.error(f"❌ This will cause 502 errors!")
    
    logger.info(f"🚀 Binding to 0.0.0.0:{port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
