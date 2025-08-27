import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class WorkoutMixin:
    async def _tool_get_workout_context(self, input_data: Dict, team_member, message_text: str):  # type: ignore[override]
        return {"success": False, "note": "Workout integration modularized placeholder"}
