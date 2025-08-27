"""Infrastructure layer: Repository interfaces and implementations."""
from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
from sqlalchemy.orm import Session
from database.models import Team, TeamMember, Meeting


class TeamRepository(ABC):
    """Repository interface for Team operations."""
    
    @abstractmethod
    def get_by_id(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        pass
    
    @abstractmethod
    def get_members(self, team_id: str) -> List[TeamMember]:
        """Get all members of a team."""
        pass


class MeetingRepository(ABC):
    """Repository interface for Meeting operations."""
    
    @abstractmethod
    def get_upcoming(self, team_id: str, limit: int = 10) -> List[Meeting]:
        """Get upcoming meetings for a team."""
        pass
    
    @abstractmethod
    def get_latest(self, team_id: str) -> Optional[Meeting]:
        """Get the latest upcoming meeting for a team."""
        pass
    
    @abstractmethod
    def save(self, meeting: Meeting) -> None:
        """Save a meeting."""
        pass
    
    @abstractmethod
    def delete(self, meeting: Meeting) -> None:
        """Delete a meeting."""
        pass


class SqlAlchemyTeamRepository(TeamRepository):
    """SQLAlchemy implementation of TeamRepository."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, team_id: str) -> Optional[Team]:
        return self.db.query(Team).filter(Team.id == team_id).first()
    
    def get_members(self, team_id: str) -> List[TeamMember]:
        return self.db.query(TeamMember).filter(TeamMember.team_id == team_id).all()


class SqlAlchemyMeetingRepository(MeetingRepository):
    """SQLAlchemy implementation of MeetingRepository."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_upcoming(self, team_id: str, limit: int = 10) -> List[Meeting]:
        from utils.time import utc_now
        return self.db.query(Meeting).filter(
            Meeting.team_id == team_id,
            Meeting.scheduled_time > utc_now()
        ).order_by(Meeting.scheduled_time).limit(limit).all()
    
    def get_latest(self, team_id: str) -> Optional[Meeting]:
        from utils.time import utc_now
        return self.db.query(Meeting).filter(
            Meeting.team_id == team_id,
            Meeting.scheduled_time > utc_now()
        ).order_by(Meeting.scheduled_time).first()
    
    def save(self, meeting: Meeting) -> None:
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
    
    def delete(self, meeting: Meeting) -> None:
        self.db.delete(meeting)
        self.db.commit()
