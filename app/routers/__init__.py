"""Aggregate FastAPI routers for inclusion in the application."""
from . import public, webhook, admin, debug, tools, health

all_routers = [
    public.router,
    webhook.router,
    admin.router,
    debug.router,
    tools.router,
    health.router,
]
