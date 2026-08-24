"""FastAPI Endpoints for MCP Tool Discovery, Parallel Multi-Agent Travel Graph, and SSE Streaming."""

import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.api.deps import get_current_active_user
from app.core.mcp import mcp_manager
from app.graphs.mcp.builder import MCPTravelGraphBuilder, create_mcp_travel_graph
from app.schemas.auth import UserResponse
from app.schemas.mcp import (
    MCPToolsListResponse,
    MCPTravelRequest,
    MCPTravelResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


@router.get(
    "/tools",
    response_model=MCPToolsListResponse,
    summary="List Registered MCP Servers & Tools",
    description="Returns active MCP servers, connection statuses, and all discovered tools.",
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


@router.post(
    "/travel/run",
    response_model=MCPTravelResponse,
    summary="Run MCP Multi-Agent Travel Pipeline (Synchronous)",
    description="Executes concurrent Airbnb & Weather agents and synthesizes a full travel & accommodation guide.",
)
async def run_mcp_travel(
    payload: MCPTravelRequest,
    current_user: UserResponse = Depends(get_current_active_user),
) -> MCPTravelResponse:
    """Executes the multi-agent travel graph synchronously."""
    logger.info(f"User '{current_user.email}' requested MCP travel run for: '{payload.topic[:60]}'")
    try:
        graph = create_mcp_travel_graph()
        initial_state = {
            "topic": payload.topic,
            "knowledge": [],
            "airbnb_report": "",
            "weather_report": "",
            "summary": "",
        }

        result = await graph.ainvoke(initial_state)

        return MCPTravelResponse(
            topic=payload.topic,
            airbnb_report=result.get("airbnb_report", ""),
            weather_report=result.get("weather_report", ""),
            final_plan=result.get("summary", ""),
            servers_used=["airbnb", "weather"],
        )
    except Exception as exc:
        logger.error(f"Error in run_mcp_travel: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP Travel execution failed: {str(exc)}",
        )


@router.post(
    "/travel/stream",
    summary="Stream MCP Travel Pipeline with Live Hints and Token Generation",
    description="Streams real-time agent progress hints and final tour guide token generation via SSE.",
)
async def stream_mcp_travel(
    payload: MCPTravelRequest,
    current_user: UserResponse = Depends(get_current_active_user),
) -> StreamingResponse:
    """Streams live multi-agent execution events and token chunks."""
    logger.info(f"User '{current_user.email}' streaming MCP travel for: '{payload.topic[:60]}'")

    async def event_generator() -> AsyncGenerator[str, None]:
        graph = create_mcp_travel_graph()
        initial_state = {
            "topic": payload.topic,
            "knowledge": [],
            "airbnb_report": "",
            "weather_report": "",
            "summary": "",
        }

        # Initial hint
        yield f"data: {json.dumps({'event': 'hint', 'agent': 'dispatcher', 'data': f'Initiating concurrent MCP travel intelligence for: {payload.topic[:50]}...'})}\n\n"

        seen_nodes = set()

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                event_name = event.get("event")
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node", "")
                tags = event.get("tags", [])

                # Emitting node transition hints
                if node_name and node_name not in seen_nodes:
                    seen_nodes.add(node_name)
                    if node_name == "airbnbAgent":
                        hint = "Airbnb Agent querying accommodation MCP server and property listings..."
                    elif node_name == "weatherAgent":
                        hint = "Weather Agent fetching localized forecasts and travel conditions..."
                    elif node_name == "tourAgent":
                        hint = "Tour Guide Agent synthesizing accommodations, weather, and day-by-day itinerary..."
                    else:
                        hint = f"Executing node: {node_name}"

                    yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

                # Token streaming for Tour Guide synthesis
                if event_name == "on_chat_model_stream" and "TourGuideExpert" in tags:
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_text = chunk.content
                        if isinstance(token_text, list):
                            token_text = "".join(
                                [p.get("text", "") if isinstance(p, dict) else str(p) for p in token_text]
                            )
                        yield f"data: {json.dumps({'event': 'token', 'agent': 'tourAgent', 'data': token_text})}\n\n"

            yield f"data: {json.dumps({'event': 'done', 'data': 'Travel planning and accommodation intelligence complete.'})}\n\n"
        except Exception as exc:
            logger.error(f"Error streaming MCP travel: {exc}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'data': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/travel/mermaid",
    response_class=PlainTextResponse,
    summary="Get MCP Travel Graph Mermaid Flowchart",
    description="Returns Mermaid diagram definition for the parallel MCP multi-agent workflow.",
)
async def get_mcp_mermaid():
    """Returns Mermaid diagram definition of the compiled MCP travel graph."""
    builder = MCPTravelGraphBuilder()
    return builder.get_mermaid_graph()
