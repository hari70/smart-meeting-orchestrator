"""
MINIMAL FastAPI app for Railway deployment testing
"""
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "running", "message": "Minimal FastAPI app working"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
