"""FastAPI Endpoints for MCP Tool Discovery, Harry Potter QA, Airbnb Travel Graph, and SSE Streaming."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.api.deps import get_current_active_user
from app.core.mcp import mcp_manager
from app.core.streaming import stream_graph_sse
from app.graphs.mcp.builder import (
    MCPTravelGraphBuilder,
    create_airbnb_graph,
    create_hp_graph,
    create_mcp_travel_graph,
)
from app.schemas.auth import UserResponse
from app.schemas.mcp import (
    MCPRequest,
    MCPResponse,
    MCPToolsListResponse,
    MCPTravelRequest,
    MCPTravelResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


# ==============================================================================
# 1. MCP Tools Registry Discovery
# ==============================================================================

@router.get(
    "/tools",
    response_model=MCPToolsListResponse,
    summary="List Registered MCP Servers & Discovered Tools",
    description="Returns connected MCP stdio servers, status health, and discovered tools.",
)
async def list_mcp_tools(
    current_user: UserResponse = Depends(get_current_active_user),
) -> MCPToolsListResponse:
    """Returns connected MCP servers and available tools."""
    server_status = mcp_manager.get_server_status()
    total_tools = sum(s.get("tools_count", 0) for s in server_status.values())
    return MCPToolsListResponse(
        status="ok",
        servers=server_status,
        total_tools=total_tools,
    )


# ==============================================================================
# 2. Dedicated SSE Streaming Generators (Completely Decoupled)
# ==============================================================================

async def _stream_harry_potter_qa(topic: str) -> AsyncGenerator[str, None]:
    """Dedicated SSE generator for Harry Potter Universe QA via Pinecone MCP."""
    graph = create_hp_graph()
    initial_state = {
        "topic": topic,
        "mode": "harry_potter",
        "knowledge": [],
        "hp_report": "",
        "summary": "",
    }
    initial_event = {
        "event": "hint",
        "agent": "dispatcher",
        "data": f"Initiating Harry Potter Universe Question Answering for: {topic[:50]}...",
    }

    def node_start_hint(node_name: str) -> str:
        if node_name == "hpSearchAgent":
            return f"Harry Potter Vector Retrieval Agent: Querying 'hpvdb-openai' Pinecone index for: '{topic[:45]}...'"
        return "Master Harry Potter Lore Scholar: Synthesizing retrieved book records into canonical answer..."

    def node_end_hint(node_name: str, output: Dict[str, Any]) -> str:
        if node_name == "hpSearchAgent":
            return "Harry Potter Vector Retrieval Agent: Book passages retrieved and verified."
        return "Master Harry Potter Lore Scholar: Finalized canonical answer."

    def tool_start_hint(tool_name: str, tool_input: Any) -> str:
        if "rerank" in tool_name.lower():
            return f"Pinecone Neural Reranker [{tool_name}]: Cross-scoring candidate passages with 'pinecone-rerank-v0'..."
        elif "multihop" in tool_name.lower():
            return f"Pinecone Multi-Hop Search [{tool_name}]: Executing sequential multi-stage retrieval..."
        return f"Pinecone MCP Tool [{tool_name}]: Searching Harry Potter vector records in 'hpvdb-openai'..."

    def tool_end_hint(tool_name: str, tool_output: Any) -> str:
        if "rerank" in tool_name.lower():
            return f"Pinecone Neural Reranker [{tool_name}]: Top candidate passages successfully scored and ranked."
        elif "multihop" in tool_name.lower():
            return f"Pinecone Multi-Hop Search [{tool_name}]: Multi-stage candidate passages retrieved."
        return f"Pinecone MCP Tool [{tool_name}]: Retrieved matching book passages & metadata."

    async for chunk in stream_graph_sse(
        graph=graph,
        inputs=initial_state,
        config={},
        stream_tags={"HPLoreScholar"},
        graph_nodes={"hpSearchAgent", "hpLoreScholar"},
        initial_event=initial_event,
        node_start_hint=node_start_hint,
        node_end_hint=node_end_hint,
        tool_start_hint=tool_start_hint,
        tool_end_hint=tool_end_hint,
        stream_format="mcp",
        target_agent_name="hpLoreScholar",
        completion_message="Harry Potter Universe answer synthesized successfully.",
    ):
        yield chunk


async def _stream_airbnb_search(topic: str) -> AsyncGenerator[str, None]:
    """Dedicated SSE generator for Airbnb Accommodation & Weather search via OpenBNB MCP."""
    graph = create_airbnb_graph()
    initial_state = {
        "topic": topic,
        "mode": "airbnb",
        "knowledge": [],
        "airbnb_report": "",
        "weather_report": "",
        "summary": "",
    }
    initial_event = {
        "event": "hint",
        "agent": "dispatcher",
        "data": f"Initiating Airbnb Accommodation & Weather Search for: {topic[:50]}...",
    }

    def node_start_hint(node_name: str) -> str:
        if node_name == "airbnbAgent":
            return f"Airbnb Agent: Searching properties and accommodations for: '{topic[:45]}...'"
        elif node_name == "weatherAgent":
            return f"Weather Agent: Analyzing meteorological conditions for: '{topic[:45]}...'"
        return "Master Tour Guide: Synthesizing lodging options & weather outlook into itinerary..."

    def node_end_hint(node_name: str, output: Dict[str, Any]) -> str:
        if node_name == "airbnbAgent":
            return "Airbnb Agent: Curated top property options and stay pricing."
        elif node_name == "weatherAgent":
            return "Weather Agent: Prepared climate advisories and temperature summary."
        return "Master Tour Guide Expert: Finalized travel plan and accommodation guide."

    def tool_start_hint(tool_name: str, tool_input: Any) -> str:
        loc = (tool_input.get("location") or tool_input.get("query") or topic[:30]) if isinstance(tool_input, dict) else topic[:30]
        if "airbnb" in tool_name.lower() or "listing" in tool_name.lower():
            return f"Airbnb MCP Tool: Querying property catalog in '{loc}'..."
        elif "weather" in tool_name.lower():
            return f"Weather Tool: Fetching 3-day forecast for '{loc}'..."
        return f"Tool [{tool_name}]: Executing lookup..."

    def tool_end_hint(tool_name: str, tool_output: Any) -> str:
        return f"Tool [{tool_name}]: Retrieved structured travel data."

    async for chunk in stream_graph_sse(
        graph=graph,
        inputs=initial_state,
        config={},
        stream_tags={"TourGuideExpert"},
        graph_nodes={"airbnbAgent", "weatherAgent", "tourAgent"},
        initial_event=initial_event,
        node_start_hint=node_start_hint,
        node_end_hint=node_end_hint,
        tool_start_hint=tool_start_hint,
        tool_end_hint=tool_end_hint,
        stream_format="mcp",
        target_agent_name="tourAgent",
        completion_message="Travel & accommodation guide ready.",
    ):
        yield chunk


# ==============================================================================
# 3. Synchronous & Streaming Endpoints
# ==============================================================================

@router.post(
    "/stream",
    summary="Stream MCP Pipeline with Live SSE Events",
    description="Streams real-time agent hints and token generation for either Harry Potter QA or Airbnb Search.",
)
@router.post("/travel/stream", include_in_schema=False)
async def stream_mcp(
    payload: MCPRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
) -> StreamingResponse:
    """Dispatches to the dedicated SSE stream based on mode ('harry_potter' vs 'airbnb')."""
    if "travel" in req.url.path and "mode" not in payload.model_fields_set:
        mode = "airbnb"
    else:
        mode = payload.mode if payload.mode in ["harry_potter", "airbnb"] else "harry_potter"

    logger.info(f"User '{current_user.email}' streaming MCP pipeline [mode={mode}] for: '{payload.topic[:60]}'")

    if mode == "harry_potter":
        generator = _stream_harry_potter_qa(payload.topic)
    else:
        generator = _stream_airbnb_search(payload.topic)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Backwards compatibility alias
stream_mcp_travel = stream_mcp


@router.post(
    "/run",
    response_model=MCPResponse,
    summary="Run MCP Pipeline Synchronously",
    description="Executes either Harry Potter Universe QA or Airbnb Search synchronously.",
)
@router.post("/travel/run", response_model=MCPResponse, include_in_schema=False)
async def run_mcp(
    payload: MCPRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
) -> MCPResponse:
    """Executes the selected MCP workflow synchronously."""
    if "travel" in req.url.path and "mode" not in payload.model_fields_set:
        mode = "airbnb"
    else:
        mode = payload.mode if payload.mode in ["harry_potter", "airbnb"] else "harry_potter"
    logger.info(f"User '{current_user.email}' requested MCP run [mode={mode}] for: '{payload.topic[:60]}'")

    try:
        if mode == "harry_potter":
            graph = create_hp_graph()
            initial_state = {
                "topic": payload.topic,
                "mode": "harry_potter",
                "knowledge": [],
                "hp_report": "",
                "summary": "",
            }
            result = await graph.ainvoke(initial_state)
            return MCPResponse(
                topic=payload.topic,
                mode="harry_potter",
                final_plan=result.get("summary", ""),
                hp_report=result.get("hp_report", ""),
                servers_used=["pinecone"],
            )
        else:
            graph = create_airbnb_graph()
            initial_state = {
                "topic": payload.topic,
                "mode": "airbnb",
                "knowledge": [],
                "airbnb_report": "",
                "weather_report": "",
                "summary": "",
            }
            result = await graph.ainvoke(initial_state)
            return MCPResponse(
                topic=payload.topic,
                mode="airbnb",
                final_plan=result.get("summary", ""),
                airbnb_report=result.get("airbnb_report", ""),
                weather_report=result.get("weather_report", ""),
                servers_used=["airbnb", "weather"],
            )
    except Exception as exc:
        logger.error(f"Error in run_mcp: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP execution failed: {str(exc)}",
        )


# Backwards compatibility alias
run_mcp_travel = run_mcp


@router.get(
    "/mermaid",
    response_class=PlainTextResponse,
    summary="Get MCP Graph Mermaid Flowchart",
    description="Returns Mermaid diagram definition for the specified MCP mode ('harry_potter' or 'airbnb').",
)
@router.get("/travel/mermaid", response_class=PlainTextResponse, include_in_schema=False)
async def get_mcp_mermaid(req: Request, mode: Optional[str] = None):
    """Returns Mermaid diagram definition for the selected mode."""
    if "travel" in req.url.path and mode is None:
        mode_clean = "airbnb"
    else:
        mode_clean = mode if mode in ["harry_potter", "airbnb"] else "harry_potter"
    builder = MCPTravelGraphBuilder()
    return builder.get_mermaid_graph(mode=mode_clean)

