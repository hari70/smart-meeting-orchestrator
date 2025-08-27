"""Domain layer: Domain events and event dispatcher."""
from abc import ABC, abstractmethod
from typing import Protocol, List, Dict
from dataclasses import dataclass
from database.models import Meeting


@dataclass
class DomainEvent(ABC):
    """Base class for domain events."""
    pass


@dataclass
class MeetingScheduled(DomainEvent):
    """Event fired when a meeting is scheduled."""
    meeting: Meeting


@dataclass
class MeetingCancelled(DomainEvent):
    """Event fired when a meeting is cancelled."""
    meeting: Meeting


class EventHandler(Protocol):
    """Interface for event handlers."""
    
    async def handle(self, event: DomainEvent) -> None:
        """Handle the domain event."""
        pass


class EventDispatcher:
    """Simple event dispatcher for domain events."""
    
    def __init__(self):
        self._handlers: Dict[type, List[EventHandler]] = {}
    
    def register_handler(self, event_type: type, handler: EventHandler) -> None:
        """Register an event handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all registered handlers."""
        event_type = type(event)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                await handler.handle(event)


# Global event dispatcher instance
event_dispatcher = EventDispatcher()
