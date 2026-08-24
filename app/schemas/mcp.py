"""Pydantic Request/Response Models and LangGraph State for MCP Workflows."""

from typing import Annotated, Any, Dict, List, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class MCPTravelState(TypedDict):
    """State definition for the MCP Travel & Weather multi-agent LangGraph workflow."""

    topic: str
    knowledge: Annotated[List[AnyMessage], add_messages]
    airbnb_report: str
    weather_report: str
    summary: str


class MCPTravelRequest(BaseModel):
    """Request payload for executing the MCP Travel Graph."""

    topic: str = Field(
        ...,
        description="Travel destination, lodging preferences, budget, and dates",
        examples=["Find me the top 5 Airbnb in Darjeeling for next 3 days within 8000 for 2 people?"],
        min_length=3,
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session or thread identifier",
    )


class MCPTravelResponse(BaseModel):
    """Response payload containing the synthesized travel guide and agent reports."""

    topic: str
    airbnb_report: str
    weather_report: str
    final_plan: str
    servers_used: List[str] = Field(default_factory=lambda: ["airbnb", "weather"])


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
