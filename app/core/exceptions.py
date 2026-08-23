"""Custom Application Exceptions and Handlers."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class BaseAppException(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentExecutionError(BaseAppException):
    """Raised when an LLM Agent or Tool fails during execution."""
    pass


class GraphExecutionError(BaseAppException):
    """Raised when LangGraph node execution or state transition fails."""
    pass


class CheckpointError(BaseAppException):
    """Raised when saving or loading checkpoint state fails."""
    pass


class DatabaseConnectionError(BaseAppException):
    """Raised when database connection pool fails or times out."""
    pass


class RerankerError(BaseAppException):
    """Raised when hybrid retrieval or cross-encoder reranking encounters an error."""
    pass


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard exception handlers with FastAPI application."""

    @app.exception_handler(BaseAppException)
    async def base_app_exception_handler(request: Request, exc: BaseAppException):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AgentExecutionError)
    async def agent_execution_error_handler(request: Request, exc: AgentExecutionError):
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "AgentExecutionError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(GraphExecutionError)
    async def graph_execution_error_handler(request: Request, exc: GraphExecutionError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "GraphExecutionError",
                "message": exc.message,
                "details": exc.details,
            },
        )
