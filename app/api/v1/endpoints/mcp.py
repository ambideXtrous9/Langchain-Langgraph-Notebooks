"""FastAPI Endpoints for MCP Tool Discovery, Harry Potter QA, Airbnb Travel Graph, and SSE Streaming."""

import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.api.deps import get_current_active_user
from app.core.mcp import mcp_manager
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

    yield f"data: {json.dumps({'event': 'hint', 'agent': 'dispatcher', 'data': f'Initiating Harry Potter Universe Question Answering for: {topic[:50]}...'})}\n\n"

    seen_start = set()
    seen_end = set()
    tokens_streamed = False

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event")
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")
            tags = event.get("tags", [])

            # Node Start Events
            if event_type in ["on_chain_start", "on_chat_model_start"] and node_name in ["hpSearchAgent", "hpLoreScholar"] and node_name not in seen_start:
                seen_start.add(node_name)
                if node_name == "hpSearchAgent":
                    hint = f"Harry Potter Vector Retrieval Agent: Querying 'hpvdb-openai' Pinecone index for: '{topic[:45]}...'"
                else:
                    hint = "Master Harry Potter Lore Scholar: Synthesizing retrieved book records into canonical answer..."
                yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

            # Pinecone Tool Events
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "pinecone_tool")
                tool_hint = f"Pinecone MCP Tool [{tool_name}]: Searching Harry Potter vector records in 'hpvdb-openai'..."
                yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'data': tool_hint})}\n\n"

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "pinecone_tool")
                tool_hint = f"Pinecone MCP Tool [{tool_name}]: Retrieved matching book passages & metadata."
                yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # Node End Events
            elif event_type == "on_chain_end" and node_name in ["hpSearchAgent", "hpLoreScholar"] and node_name not in seen_end:
                seen_end.add(node_name)
                if node_name == "hpSearchAgent":
                    hint = "Harry Potter Vector Retrieval Agent: Book passages retrieved and verified."
                else:
                    hint = "Master Harry Potter Lore Scholar: Finalized canonical answer."
                    output = event.get("data", {}).get("output") or {}
                    if isinstance(output, dict) and "summary" in output:
                        final_summary = output["summary"]
                yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

            # Token Streaming from Scholar
            elif event_type == "on_chat_model_stream" and "HPLoreScholar" in tags:
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_text = chunk.content
                    if isinstance(token_text, list):
                        token_text = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in token_text])
                    if token_text:
                        tokens_streamed = True
                        yield f"data: {json.dumps({'event': 'token', 'agent': 'hpLoreScholar', 'data': token_text})}\n\n"

        if not tokens_streamed and 'final_summary' in locals() and final_summary:
            yield f"data: {json.dumps({'event': 'token', 'agent': 'hpLoreScholar', 'data': final_summary})}\n\n"

        yield f"data: {json.dumps({'event': 'done', 'data': 'Harry Potter Universe answer synthesized successfully.'})}\n\n"

    except Exception as exc:
        logger.error(f"Error streaming Harry Potter QA: {exc}", exc_info=True)
        yield f"data: {json.dumps({'event': 'error', 'data': str(exc)})}\n\n"


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

    yield f"data: {json.dumps({'event': 'hint', 'agent': 'dispatcher', 'data': f'Initiating Airbnb Accommodation & Weather Search for: {topic[:50]}...'})}\n\n"

    seen_start = set()
    seen_end = set()
    tokens_streamed = False

    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event")
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")
            tags = event.get("tags", [])

            # Node Start Events
            if event_type in ["on_chain_start", "on_chat_model_start"] and node_name in ["airbnbAgent", "weatherAgent", "tourAgent"] and node_name not in seen_start:
                seen_start.add(node_name)
                if node_name == "airbnbAgent":
                    hint = f"Airbnb Agent: Searching properties and accommodations for: '{topic[:45]}...'"
                elif node_name == "weatherAgent":
                    hint = f"Weather Agent: Analyzing meteorological conditions for: '{topic[:45]}...'"
                else:
                    hint = "Master Tour Guide: Synthesizing lodging options & weather outlook into itinerary..."
                yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

            # Tool Events
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "mcp_tool")
                tool_input = event.get("data", {}).get("input") or {}
                if "airbnb" in tool_name.lower() or "listing" in tool_name.lower():
                    loc = tool_input.get("location") or tool_input.get("query") or topic[:30]
                    tool_hint = f"Airbnb MCP Tool: Querying property catalog in '{loc}'..."
                elif "weather" in tool_name.lower():
                    loc = tool_input.get("location") or tool_input.get("query") or topic[:30]
                    tool_hint = f"Weather Tool: Fetching 3-day forecast for '{loc}'..."
                else:
                    tool_hint = f"Tool [{tool_name}]: Executing lookup..."
                yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'data': tool_hint})}\n\n"

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "mcp_tool")
                tool_hint = f"Tool [{tool_name}]: Retrieved structured travel data."
                yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # Node End Events
            elif event_type == "on_chain_end" and node_name in ["airbnbAgent", "weatherAgent", "tourAgent"] and node_name not in seen_end:
                seen_end.add(node_name)
                if node_name == "airbnbAgent":
                    hint = "Airbnb Agent: Curated top property options and stay pricing."
                elif node_name == "weatherAgent":
                    hint = "Weather Agent: Prepared climate advisories and temperature summary."
                else:
                    hint = "Master Tour Guide Expert: Finalized travel plan and accommodation guide."
                    output = event.get("data", {}).get("output") or {}
                    if isinstance(output, dict) and "summary" in output:
                        final_summary = output["summary"]
                yield f"data: {json.dumps({'event': 'hint', 'agent': node_name, 'data': hint})}\n\n"

            # Token Streaming from Tour Guide
            elif event_type == "on_chat_model_stream" and "TourGuideExpert" in tags:
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token_text = chunk.content
                    if isinstance(token_text, list):
                        token_text = "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in token_text])
                    if token_text:
                        tokens_streamed = True
                        yield f"data: {json.dumps({'event': 'token', 'agent': 'tourAgent', 'data': token_text})}\n\n"

        if not tokens_streamed and 'final_summary' in locals() and final_summary:
            yield f"data: {json.dumps({'event': 'token', 'agent': 'tourAgent', 'data': final_summary})}\n\n"

        yield f"data: {json.dumps({'event': 'done', 'data': 'Travel & accommodation guide ready.'})}\n\n"

    except Exception as exc:
        logger.error(f"Error streaming Airbnb search: {exc}", exc_info=True)
        yield f"data: {json.dumps({'event': 'error', 'data': str(exc)})}\n\n"


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
    current_user: UserResponse = Depends(get_current_active_user),
) -> StreamingResponse:
    """Dispatches to the dedicated SSE stream based on mode ('harry_potter' vs 'airbnb')."""
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
    current_user: UserResponse = Depends(get_current_active_user),
) -> MCPResponse:
    """Executes the selected MCP workflow synchronously."""
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
async def get_mcp_mermaid(mode: str = "harry_potter"):
    """Returns Mermaid diagram definition for the selected mode."""
    mode_clean = mode if mode in ["harry_potter", "airbnb"] else "harry_potter"
    builder = MCPTravelGraphBuilder()
    return builder.get_mermaid_graph(mode=mode_clean)

