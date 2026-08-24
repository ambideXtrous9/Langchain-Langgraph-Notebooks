"""FastAPI Endpoints for MCP Tool Discovery, Parallel Multi-Agent Travel Graph, and SSE Streaming."""

import json
import logging
from typing import Any, AsyncGenerator, Dict
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
        topic = payload.topic
        initial_state = {
            "topic": topic,
            "knowledge": [],
            "airbnb_report": "",
            "weather_report": "",
            "summary": "",
        }

        # 1. Initial kickoff event specialized to user query
        yield f"data: {json.dumps({'event': 'hint', 'agent': 'dispatcher', 'data': f'Initiating concurrent MCP travel intelligence for: {topic[:50]}...'})}\n\n"

        seen_start_nodes = set()
        seen_end_nodes = set()
        seen_tools = set()
        tokens_streamed = False

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event")
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node", "")
                tags = event.get("tags", [])

                # 2a. Dynamic Node Start Hints specialized to user topic
                if event_type == "on_chain_start" and node_name in ["airbnbAgent", "weatherAgent", "tourAgent"] and node_name not in seen_start_nodes:
                    seen_start_nodes.add(node_name)
                    if node_name == "airbnbAgent":
                        hint = f"Airbnb Agent: Analyzing accommodation criteria and searching available listings for '{topic[:45]}...'"
                    elif node_name == "weatherAgent":
                        hint = f"Weather Agent: Analyzing atmospheric conditions and climate forecast for '{topic[:45]}...'"
                    elif node_name == "tourAgent":
                        hint = f"Tour Guide Expert: Cross-referencing accommodation amenities with weather outlook to assemble final itinerary for '{topic[:45]}...'"
                    else:
                        hint = f"Executing Agent: {node_name} for '{topic[:40]}...'"

                    yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

                # 2b. Dynamic Tool Execution Start Hints (specialized with tool arguments)
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    tool_input = event.get("data", {}).get("input") or {}
                    tool_call_id = event.get("run_id", tool_name)

                    if tool_call_id not in seen_tools:
                        seen_tools.add(tool_call_id)
                        if "weather" in tool_name.lower():
                            location = tool_input.get("location") or tool_input.get("query") or topic[:30]
                            days = tool_input.get("days", 3)
                            tool_hint = f"Weather Tool: Fetching meteorological forecast for '{location}' ({days} days)..."
                        elif "airbnb" in tool_name.lower() or "listing" in tool_name.lower():
                            loc = tool_input.get("location") or tool_input.get("query") or topic[:30]
                            adults = tool_input.get("adults", 2)
                            tool_hint = f"Airbnb MCP Tool: Querying property catalog in '{loc}' for {adults} guests..."
                        else:
                            input_preview = str(tool_input)[:40]
                            tool_hint = f"Tool [{tool_name}]: Executing specialized lookup with params ({input_preview})..."

                        yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'data': tool_hint})}\n\n"

                # 2c. Dynamic Tool Completion Hints
                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    tool_hint = f"Tool [{tool_name}]: Retrieved structured intelligence for '{topic[:35]}...'"
                    yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'data': tool_hint})}\n\n"

                # 2d. Dynamic Node Completion Hints
                elif event_type == "on_chain_end" and node_name in ["airbnbAgent", "weatherAgent", "tourAgent"] and node_name not in seen_end_nodes:
                    seen_end_nodes.add(node_name)
                    if node_name == "airbnbAgent":
                        hint = f"Airbnb Agent: Curated top property options and stay pricing for '{topic[:40]}...'"
                    elif node_name == "weatherAgent":
                        hint = f"Weather Agent: Prepared climate advisories and temperature summary for '{topic[:40]}...'"
                    elif node_name == "tourAgent":
                        hint = f"Tour Guide Expert: Finalized travel plan and recommendations for '{topic[:40]}...'"
                    else:
                        hint = f"Completed Agent: {node_name} for '{topic[:40]}...'"

                    yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

                # 3. Token streaming ONLY from the final Tour Guide Expert synthesis node
                elif event_type == "on_chat_model_stream" and "TourGuideExpert" in tags:
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token_text = chunk.content
                        if isinstance(token_text, list):
                            token_text = "".join(
                                [p.get("text", "") if isinstance(p, dict) else str(p) for p in token_text]
                            )
                        if token_text:
                            tokens_streamed = True
                            yield f"data: {json.dumps({'event': 'token', 'agent': 'tourAgent', 'data': token_text})}\n\n"

            # 4. Final done event
            yield f"data: {json.dumps({'event': 'done', 'data': f'Travel planning and accommodation intelligence complete for {topic[:40]}...'})}\n\n"
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
