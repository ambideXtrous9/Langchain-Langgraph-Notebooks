"""Pydantic Models for Chat and Session Management Endpoints."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request payload for /generic_chat endpoint."""

    user_input: str = Field(..., description="The user's query or message", min_length=1)
    session_id: Optional[str] = Field(
        default=None, description="Optional UUID session ID. If not provided, a new one will be generated."
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional extra metadata for context or tracing."
    )


class ChatResponse(BaseModel):
    """Response payload for /generic_chat endpoint."""

    session_id: str = Field(..., description="The session ID associated with this chat history")
    response: str = Field(..., description="The AI assistant's synthesized response")


class DeleteSessionRequest(BaseModel):
    """Request payload for /delete_session endpoint."""

    session_id: str = Field(..., description="The session ID to remove from the chat history database")


class DeleteSessionResponse(BaseModel):
    """Response payload for /delete_session endpoint."""

    message: str = "Chat session deleted successfully"
    session_id: str
