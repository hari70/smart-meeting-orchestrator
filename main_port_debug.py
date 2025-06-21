# main.py - Debug port binding
from fastapi import FastAPI
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/debug")
async def debug():
    return {
        "port_env": os.getenv("PORT"),
        "all_env": {k: v for k, v in os.environ.items() if "PORT" in k or "RAILWAY" in k}
    }

if __name__ == "__main__":
    import uvicorn
    
    # Debug port assignment
    port_env = os.getenv("PORT")
    port = int(port_env) if port_env else 8000
    
    logger.info(f"🌐 PORT environment variable: {port_env}")
    logger.info(f"🚀 Starting server on 0.0.0.0:{port}")
    logger.info(f"🐍 Python version: {sys.version}")
    logger.info(f"📊 Process ID: {os.getpid()}")
    
    # List all Railway environment variables
    railway_vars = {k: v for k, v in os.environ.items() if k.startswith("RAILWAY")}
    logger.info(f"🚂 Railway environment variables: {railway_vars}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
