import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL")

def _build_engine(url: str):
    if url.startswith("sqlite"):
        # Allow multithreaded test client usage
        return create_engine(url, connect_args={"check_same_thread": False})
    elif url.startswith("postgresql"):
        # Add connection pooling and timeout settings for PostgreSQL
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 10}
        )
    return create_engine(url)

if not DATABASE_URL:
    # Fallback for local/dev/tests if not provided
    DATABASE_URL = "sqlite:///./app.db"
    print(f"Warning: DATABASE_URL not set, using fallback: {DATABASE_URL}")

try:
    engine = _build_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print(f"Database engine created successfully for: {DATABASE_URL.split('://')[0]}://...")
except Exception as e:
    print(f"Error creating database engine: {e}")
    # Create a dummy engine for now
    engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
