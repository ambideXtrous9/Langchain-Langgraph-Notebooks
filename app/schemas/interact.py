"""Pydantic Models for LangGraph Interaction, SSE Streaming, and Thread Management."""

from typing import Any, Dict, List, Optional
from pydantic import AliasChoices, BaseModel, Field


class InteractionRequest(BaseModel):
    """Request payload for /interact SSE endpoint and WebSocket."""

    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID representing persistent conversation checkpoint. If omitted, a new thread is created.",
    )
    user_input: Optional[str] = Field(
        default=None,
        description="The user's query, answer to an interrupt prompt, or feedback message.",
    )
    user_choices: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User choices, configuration dictionary, or initial tree decisions.",
    )
    useDeviceData: bool = Field(
        default=False,
        description="Flag indicating whether to process user-provided device metadata.",
    )
    userProvidedDeiveceData: Optional[str] = Field(
        default="",
        validation_alias=AliasChoices(
            "userProvidedDeiveceData",
            "user_provided_device_data",
            "userProvidedDeviceData",
        ),
        serialization_alias="userProvidedDeiveceData",
        description="Raw or structured device data string provided by the user.",
    )

    @property
    def device_data(self) -> str:
        """Returns normalized device data string."""
        return self.userProvidedDeiveceData or ""


class DeleteThreadRequest(BaseModel):
    """Request payload for /delete_thread endpoint."""

    thread_id: str = Field(..., description="The thread ID to delete from PostgreSQL checkpointer")


class DeleteThreadResponse(BaseModel):
    """Response payload for /delete_thread endpoint."""

    message: str = "Thread deleted successfully"
    thread_id: str


class GraphStateResponse(BaseModel):
    """Response payload when querying current thread checkpoint state."""

    thread_id: str
    next_nodes: List[str]
    values: Dict[str, Any]
    is_completed: bool
