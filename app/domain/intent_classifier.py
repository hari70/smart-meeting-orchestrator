"""Domain layer: Intent classification using Strategy pattern."""
import re
from typing import Protocol, Dict, List
from abc import ABC, abstractmethod


class IntentClassifier(ABC):
    """Strategy interface for classifying user intents."""
    
    @abstractmethod
    def classify(self, message: str) -> str:
        """Classify the intent of a message."""
        pass


class RegexIntentClassifier(IntentClassifier):
    """Concrete strategy using regex patterns for intent classification."""
    
    def __init__(self):
        self.patterns: Dict[str, List[str]] = {
            "schedule_meeting": [
                r"(?:family|team)?\s*(?:meeting|call)\s+about\s+(.+?)\s+(?:this|next)?\s*(week|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)",
                r"schedule\s+(?:call|meeting)\s+with\s+(.+?)\s+(?:this|next)?\s*(week|weekend|today|tomorrow)",
                r"(?:family|team)\s+(?:call|meeting)\s+(.+)"
            ],
            "list_meetings": [
                r"(?:what|when)(?:'s|'re)?\s+(?:our|my|the)?\s*(?:next|upcoming)?\s*meetings?",
                r"show\s+(?:my|our)?\s*meetings",
                r"agenda"
            ],
            "cancel_meeting": [
                r"cancel\s+(?:today's|tomorrow's|the)?\s*(?:meeting|call)",
                r"(?:delete|remove)\s+meeting"
            ],
            "availability": [
                r"(?:when|what time)\s+(?:is|are)\s+(?:we|everyone)\s+(?:free|available)",
                r"find\s+time\s+for\s+(?:meeting|call)",
                r"availability"
            ]
        }
    
    def classify(self, message: str) -> str:
        """Classify message intent using regex patterns."""
        message_lower = message.lower().strip()
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return intent
        return "general"


# Default classifier instance
default_classifier = RegexIntentClassifier()
