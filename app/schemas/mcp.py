"""Pydantic Request/Response Models and LangGraph State for MCP Workflows."""

from typing import Annotated, Any, Dict, List, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class MCPState(TypedDict, total=False):
    """Unified State definition for MCP workflows."""

    topic: str
    mode: str
    knowledge: Annotated[List[AnyMessage], add_messages]
    airbnb_report: str
    weather_report: str
    hp_report: str
    summary: str


# Backwards compatibility alias
MCPTravelState = MCPState


class MCPRequest(BaseModel):
    """Payload for executing an MCP agent workflow."""

    topic: str = Field(
        ...,
        description="Query, travel search criteria, or Harry Potter universe question",
        examples=["Explain the allegiance history of the Elder Wand across the books"],
        min_length=2,
    )
    mode: str = Field(
        default="harry_potter",
        description="Workflow mode: 'harry_potter' (HP Universe QA via Pinecone) or 'airbnb' (Airbnb Lodging & Weather)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session or thread identifier",
    )


# Backwards compatibility alias
MCPTravelRequest = MCPRequest


class MCPResponse(BaseModel):
    """Response payload containing synthesized result and mode-specific reports."""

    topic: str
    mode: str = "harry_potter"
    final_plan: str = Field(..., description="Synthesized final answer or travel itinerary")
    hp_report: Optional[str] = Field(default="", description="Retrieved Pinecone vector passages (HP mode)")
    airbnb_report: Optional[str] = Field(default="", description="Retrieved Airbnb lodging listings (Airbnb mode)")
    weather_report: Optional[str] = Field(default="", description="Retrieved 3-day weather forecast (Airbnb mode)")
    servers_used: List[str] = Field(default_factory=lambda: ["pinecone"])


# Backwards compatibility alias
MCPTravelResponse = MCPResponse


class MCPToolsListResponse(BaseModel):
    """Response model for registered MCP servers and their available tools."""

    status: str = "ok"
    servers: Dict[str, Any]
    total_tools: int


class MCPTravelStreamEvent(BaseModel):
    """Event payload for Server-Sent Events (SSE) streaming."""

    event: str = Field(..., description="Event type: 'hint', 'token', 'done', 'error'")
    agent: Optional[str] = Field(default=None, description="Originating agent name")
    data: str = Field(..., description="Content payload or token chunk")
