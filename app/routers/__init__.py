"""Aggregate FastAPI routers for inclusion in the application."""
from . import public, webhook, admin, debug

all_routers = [
    public.router,
    webhook.router,
    admin.router,
    debug.router,
]
