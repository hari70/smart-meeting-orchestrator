import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL")

def _build_engine(url: str):
    if url.startswith("sqlite"):
        # Allow multithreaded test client usage
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)

if not DATABASE_URL:
    # Fallback for local/dev/tests if not provided
    DATABASE_URL = "sqlite:///./dev.db"

engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
