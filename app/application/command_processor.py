"""Application layer: Modern command processor using patterns."""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import TeamMember
from app.domain.intent_classifier import IntentClassifier, default_classifier
from app.application.handlers import (
    ScheduleMeetingHandler, ListMeetingsHandler, 
    CancelMeetingHandler, GeneralQueryHandler
)
from app.infrastructure.repositories import SqlAlchemyMeetingRepository, SqlAlchemyTeamRepository

logger = logging.getLogger(__name__)


class ModernCommandProcessor:
    """Modern command processor using Strategy and Command patterns with MCP integration."""
    
    def __init__(self, sms_client, calendar_client, meet_client, 
                 intent_classifier: Optional[IntentClassifier] = None,
                 mcp_processor=None):
        self.sms_client = sms_client
        self.calendar_client = calendar_client
        self.meet_client = meet_client
        
        # Use provided classifier or default
        self.intent_classifier = intent_classifier or default_classifier
        
        # Initialize repositories (dependency injection)
        self._meeting_repo = None
        self._team_repo = None
        
        # Initialize handlers
        self._handlers = {}
        
        # MCP processor for LLM-powered processing
        self.mcp_processor = mcp_processor
    
    def _get_repositories(self, db: Session):
        """Lazy initialization of repositories."""
        if self._meeting_repo is None:
            self._meeting_repo = SqlAlchemyMeetingRepository(db)
            self._team_repo = SqlAlchemyTeamRepository(db)
        return self._meeting_repo, self._team_repo
    
    def _get_handler(self, intent: str, db: Session):
        """Get or create handler for intent."""
        if intent not in self._handlers:
            meeting_repo, team_repo = self._get_repositories(db)
            
            if intent == "schedule_meeting":
                self._handlers[intent] = ScheduleMeetingHandler(
                    meeting_repo, team_repo, self.calendar_client, self.meet_client
                )
            elif intent == "list_meetings":
                self._handlers[intent] = ListMeetingsHandler(meeting_repo)
            elif intent == "cancel_meeting":
                self._handlers[intent] = CancelMeetingHandler(meeting_repo, self.calendar_client)
            else:
                self._handlers[intent] = GeneralQueryHandler()
        
        return self._handlers[intent]
    
    async def process_command(self, message_text: str, team_member: TeamMember, 
                            conversation, db: Session) -> str:
        """Process command using modern architecture."""
        try:
            intent = self.intent_classifier.classify(message_text)
            logger.info(f"[MODERN_CMD] {intent} from {team_member.name}")
            
            handler = self._get_handler(intent, db)
            return await handler.handle(message_text, team_member, db)
            
        except Exception as e:
            logger.error(f"Modern command error: {e}")
            return "Sorry, I encountered an error processing your request. Please try again."
    
    # LLM-powered processing with MCP tools
    async def process_command_with_llm(self, message_text: str, team_member: TeamMember, 
                                     conversation, db: Session) -> str:
        """Process command using MCP tools and LLM for intelligent responses."""
        try:
            # Use MCP processor if available
            logger.info(f"[MCP_CMD] Checking for MCP processor: {self.mcp_processor}")
            
            if self.mcp_processor and hasattr(self.mcp_processor, 'process_command_with_llm'):
                logger.info(f"[MCP_CMD] Using MCP processor: {self.mcp_processor}, llm_enabled={getattr(self.mcp_processor, 'llm_enabled', 'unknown')}")
                return await self.mcp_processor.process_command_with_llm(
                    message_text, team_member, conversation, db
                )
            else:
                logger.warning(f"[MCP_CMD] MCP processor not available: processor={self.mcp_processor}, has_method={hasattr(self.mcp_processor or {}, 'process_command_with_llm')}")
                return await self.process_command(message_text, team_member, conversation, db)
                
        except Exception as e:
            logger.error(f"MCP command error: {e}", exc_info=True)
            # Fallback to pattern-based processing
            return await self.process_command(message_text, team_member, conversation, db)
