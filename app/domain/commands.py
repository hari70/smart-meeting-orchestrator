"""Domain layer: Command pattern for handling user intents."""
from abc import ABC, abstractmethod
from typing import Protocol, Dict, Any
from sqlalchemy.orm import Session
from database.models import TeamMember


class Command(ABC):
    """Command interface."""
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> str:
        """Execute the command with given context."""
        pass


class CommandHandler(ABC):
    """Handler interface for processing commands."""
    
    @abstractmethod
    async def handle(self, message: str, team_member: TeamMember, db: Session) -> str:
        """Handle the command."""
        pass


# Concrete command implementations will be in application layer
