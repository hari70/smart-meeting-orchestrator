class FallbackMixin:
    async def _fallback_response(self, message: str, user) -> str:  # type: ignore[override]
        ml = message.lower()
        if any(w in ml for w in ("schedule","meeting","plan")):
            return f"Hi {user.name}! AI temporarily unavailable; retry soon."
        return f"Hi {user.name}! I'm your meeting coordinator (lite mode)."
