"""WebSocket Streaming Endpoint for Real-Time Bidirectional Graph Interaction."""

import json
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from langgraph.types import Command
from app.core.auth_database import auth_db_manager
from app.core.observability import flush_langfuse, get_runnable_config
from app.core.security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()


async def authenticate_websocket(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """Validates JWT access token from query parameters or Authorization header."""
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti and await auth_db_manager.is_token_blacklisted(jti):
            return None
        email = payload.get("sub")
        if not email:
            return None
        user = await auth_db_manager.get_user_by_email(email)
        if not user or not user.get("is_active", True):
            return None
        return user
    except Exception as e:
        logger.debug(f"WebSocket authentication error: {e}")
        return None


@router.websocket("/ws/interact")
async def websocket_interact_endpoint(websocket: WebSocket):
    """Bi-directional WebSocket streaming for LangGraph interactions."""
    user = await authenticate_websocket(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: Valid JWT token required.")
        return

    await websocket.accept()
    logger.info(f"WebSocket client connected for user: {user.get('email')}")

    graph = getattr(websocket.app.state, "graph", None)
    if graph is None:
        await websocket.send_json({"type": "error", "message": "Graph engine is not initialized."})
        await websocket.close()
        return

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload: Dict[str, Any] = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON message format."})
                continue

            action = payload.get("action", "start")
            thread_id = payload.get("thread_id") or str(uuid.uuid4())
            user_input = payload.get("user_input", "")
            user_choices = payload.get("user_choices", {})
            use_device = payload.get("useDeviceData", False)
            device_data = (
                payload.get("user_provided_device_data")
                or payload.get("userProvidedDeviceData")
                or payload.get("userProvidedDeiveceData")
                or ""
            )

            thread_config = get_runnable_config(
                thread_id=thread_id,
                metadata={"user_id": user.get("id"), "email": user.get("email")},
            )

            # Send thread_id confirmation
            await websocket.send_json({"type": "thread_id", "thread_id": thread_id})

            if action == "resume":
                # Check current state
                current_state = await graph.aget_state(thread_config)
                if not current_state or not current_state.next:
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "message": "Graph execution already complete for this thread.",
                            "thread_id": thread_id,
                        }
                    )
                    continue

                graph_input = Command(
                    resume=user_input,
                    update={
                        "useDeviceData": use_device,
                        "userProvidedDeiveceData": device_data,
                        "user_provided_device_data": device_data,
                    },
                )
            else:
                graph_input = {
                    "user_choices": user_choices,
                    "feedback": user_input,
                    "useDeviceData": use_device,
                    "userProvidedDeiveceData": device_data,
                    "user_provided_device_data": device_data,
                    "chat_history": [],
                }

            token_streamed = False
            seen_ws_start_nodes = set()
            seen_ws_end_nodes = set()
            seen_ws_tools = set()

            device_label = device_data or (user_choices.get("system_tier") if isinstance(user_choices, dict) else "") or (user_choices.get("device_class") if isinstance(user_choices, dict) else "") or "enterprise system"
            prompt_summary = user_input or "policy compliance analysis"

            events = graph.astream_events(input=graph_input, config=thread_config, version="v2")

            graph_nodes = {
                "user_initpath",
                "classify_node",
                "device_summary",
                "knowledge_base",
                "reason_llm",
                "process_feedback",
            }

            async for event in events:
                event_type = event.get("event")
                event_tags = event.get("tags") or []
                node_name = event.get("name", "")

                # Node Start Hints
                if event_type == "on_chain_start" and node_name in graph_nodes and node_name not in seen_ws_start_nodes:
                    seen_ws_start_nodes.add(node_name)
                    if node_name == "user_initpath":
                        hint = f"Routing Engine: Parsing user intent, system parameters, and policy path for '{prompt_summary[:40]}...'"
                    elif node_name == "classify_node":
                        hint = f"Structured Classifier: Validating policy schema and routing compliance for '{prompt_summary[:40]}...'"
                    elif node_name == "device_summary":
                        hint = f"System Profiler: Synthesizing specifications and classification tier for '{device_label}'..."
                    elif node_name == "knowledge_base":
                        hint = f"Knowledge Base: Performing BM25 + dense retrieval for '{prompt_summary[:40]}...'"
                    elif node_name == "reason_llm":
                        hint = f"Policy Expert: Synthesizing compliance pathway and standard specification reasoning for '{prompt_summary[:40]}...'"
                    elif node_name == "process_feedback":
                        hint = "Human-in-the-Loop: Awaiting user feedback/authorization on policy guidance..."
                    else:
                        hint = f"Executing Node: {node_name}"

                    await websocket.send_json({"type": "hint", "stage": node_name, "status": "started", "content": hint})

                # Tool Execution Hints
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    tool_input = event.get("data", {}).get("input") or {}
                    tool_id = event.get("run_id", tool_name)
                    if tool_id not in seen_ws_tools:
                        seen_ws_tools.add(tool_id)
                        query_param = tool_input.get("query") if isinstance(tool_input, dict) else str(tool_input)
                        t_hint = f"Tool [{tool_name}]: Querying benchmark data for '{str(query_param)[:40]}...'..."
                        await websocket.send_json({"type": "tool_start", "tool": tool_name, "content": t_hint})

                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    t_hint = f"Tool [{tool_name}]: Benchmark intelligence retrieved for '{device_label}'"
                    await websocket.send_json({"type": "tool_end", "tool": tool_name, "content": t_hint})

                # Node Completion Hints
                elif event_type == "on_chain_end" and node_name in graph_nodes and node_name not in seen_ws_end_nodes:
                    seen_ws_end_nodes.add(node_name)
                    if node_name == "classify_node":
                        hint = f"Structured Classifier: Confirmed policy classification for '{prompt_summary[:35]}...'"
                    elif node_name == "device_summary":
                        hint = f"System Profiler: Generated technical profile for '{device_label}'"
                    elif node_name == "knowledge_base":
                        hint = f"Knowledge Base: Matched relevant policy standards and guidance documents"
                    elif node_name == "reason_llm":
                        hint = f"Policy Expert: Finalized compliance recommendations for '{device_label}'"
                    else:
                        hint = f"Completed {node_name}"

                    await websocket.send_json({"type": "hint", "stage": node_name, "status": "completed", "content": hint})

                # Token streaming from PolicyExpert or reason_llm node
                elif event_type == "on_chat_model_stream":
                    if any(tag in ["PolicyExpert", "reason_llm"] for tag in event_tags):
                        chunk = event.get("data", {}).get("chunk")
                        chunk_content = getattr(chunk, "content", "") if chunk else ""
                        if chunk_content:
                            token_streamed = True
                            await websocket.send_json({"type": "token", "content": chunk_content})

            # Check post-execution state
            post_state = await graph.aget_state(thread_config)
            is_interrupted = bool(post_state.next)

            if not token_streamed:
                # Send direct classification reply if token stream was not triggered
                classification = post_state.values.get("classification", {})
                if isinstance(classification, dict) and classification.get("reply"):
                    await websocket.send_json({"type": "token", "content": classification["reply"]})

            await websocket.send_json(
                {
                    "type": "status",
                    "thread_id": thread_id,
                    "next_nodes": list(post_state.next) if post_state.next else [],
                    "is_interrupted": is_interrupted,
                    "is_completed": not is_interrupted,
                }
            )
            flush_langfuse()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
