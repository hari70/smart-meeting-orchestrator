from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator, CHAR
import uuid
from datetime import datetime


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.

    Uses PostgreSQL UUID when available; otherwise stores as CHAR(36).
    """
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # pragma: no cover - trivial
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):  # pragma: no cover - trivial
        if value is None:
            return value
        return uuid.UUID(str(value))

Base = declarative_base()

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    team_id = Column(GUID(), ForeignKey("teams.id"))
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255))  # Added email field for calendar invites
    google_calendar_id = Column(String(100))
    preferences = Column(JSON, default={})
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    team_id = Column(GUID(), ForeignKey("teams.id"))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    scheduled_time = Column(DateTime)
    duration_minutes = Column(Integer, default=60)
    google_meet_link = Column(String(500))
    google_calendar_event_id = Column(String(200))
    agenda = Column(JSON, default=[])
    created_by_phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), nullable=False)
    team_id = Column(GUID(), ForeignKey("teams.id"))
    context = Column(JSON, default={})
    last_activity = Column(DateTime, default=datetime.utcnow)
