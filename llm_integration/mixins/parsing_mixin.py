import logging, re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class ParsingMixin:
    def _parse_datetime_bulletproof(self, time_str: str, original_message: str) -> Optional[datetime]:  # type: ignore[override]
        # Moved from IntelligentCoordinator for modularity
        logger.info(f"🛡️ [BULLETPROOF PARSER] Input: '{time_str}' from message: '{original_message}'")
        now = datetime.now()
        try:
            if time_str and ('T' in time_str or '+' in time_str or 'Z' in time_str):
                try:
                    return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                except Exception:
                    pass
            message_lower = original_message.lower()
            target_date = (now + timedelta(days=1)).date()
            if "tomorrow" in message_lower:
                target_date = (now + timedelta(days=1)).date()
            elif "today" in message_lower:
                target_date = now.date()
            weekdays = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6}
            for day, num in weekdays.items():
                if day in message_lower:
                    ahead = (num - now.weekday()) % 7 or 7
                    target_date = (now + timedelta(days=ahead)).date()
                    break
            target_hour, target_minute = 19, 0
            time_patterns = [
                (r'(\d{1,2}):(\d{2})\s*(am|pm)', 'hm_ampm'),
                (r'(\d{1,2})\s*(am|pm)', 'h_ampm'),
                (r'(\d{1,2}):(\d{2})', 'hm24')
            ]
            for pattern, kind in time_patterns:
                m = re.search(pattern, message_lower)
                if m:
                    if kind == 'hm_ampm':
                        h = int(m.group(1)); minute = int(m.group(2)); ap = m.group(3)
                        if ap == 'pm' and h != 12: h += 12
                        if ap == 'am' and h == 12: h = 0
                        target_hour, target_minute = h, minute
                    elif kind == 'h_ampm':
                        h = int(m.group(1)); ap = m.group(2)
                        if ap == 'pm' and h != 12: h += 12
                        if ap == 'am' and h == 12: h = 0
                        target_hour = h
                    else:
                        target_hour, target_minute = int(m.group(1)), int(m.group(2))
                    break
            return datetime.combine(target_date, datetime.min.time().replace(hour=target_hour, minute=target_minute))
        except Exception:
            return datetime.combine((now + timedelta(days=1)).date(), datetime.min.time().replace(hour=19))
