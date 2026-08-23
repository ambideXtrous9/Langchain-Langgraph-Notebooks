"""Health Check and Graph Visualization Endpoints."""

from typing import Any, Dict
from fastapi import APIRouter, Request, status
from fastapi.responses import PlainTextResponse
from app.core.config import settings

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint reporting API version and database connection status."""
    db_status = "connected" if hasattr(request.app.state, "db_pool") and request.app.state.db_pool else "in-memory"

    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "langfuse_enabled": settings.LANGFUSE_ENABLED,
    }


@router.get("/graph/mermaid", response_class=PlainTextResponse, tags=["Graph"])
async def get_graph_mermaid(request: Request) -> str:
    """Returns the Mermaid graph definition of the active LangGraph workflow."""
    if hasattr(request.app.state, "graph") and request.app.state.graph:
        return request.app.state.graph.get_graph().draw_mermaid()
    return "Graph not initialized yet."
