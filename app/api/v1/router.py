"""API Version 1 Router Aggregation."""

from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, chat, sql, interact, websocket, research, mcp

api_router = APIRouter()

# Register endpoint modules
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(sql.router)
api_router.include_router(interact.router)
api_router.include_router(websocket.router)
api_router.include_router(research.router)
api_router.include_router(mcp.router)
