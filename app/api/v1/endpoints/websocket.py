"""WebSocket Streaming Endpoint for Real-Time Bidirectional Graph Interaction."""

import json
import logging
import uuid
from typing import Any, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
from app.core.observability import flush_langfuse, get_runnable_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/interact")
async def websocket_interact_endpoint(websocket: WebSocket):
    """Bi-directional WebSocket streaming for LangGraph interactions.

    Protocol:
    - Client sends:
        {"action": "start", "user_choices": {...}, "user_input": "...", "useDeviceData": bool, ...}
      or
        {"action": "resume", "thread_id": "...", "user_input": "..."}
    - Server streams:
        {"type": "thread_id", "thread_id": "..."}
        {"type": "token", "content": "..."}
        {"type": "status", "next_nodes": [...], "is_interrupted": bool}
        {"type": "complete"}
    """
    await websocket.accept()
    logger.info("WebSocket client connected.")

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
            device_data = payload.get("userProvidedDeiveceData", "")

            thread_config = get_runnable_config(thread_id=thread_id)

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
                    update={"useDeviceData": use_device, "userProvidedDeiveceData": device_data},
                )
            else:
                graph_input = {
                    "user_choices": user_choices,
                    "feedback": user_input,
                    "useDeviceData": use_device,
                    "userProvidedDeiveceData": device_data,
                    "chat_history": [],
                }

            token_streamed = False
            seen_ws_start_nodes = set()
            seen_ws_end_nodes = set()
            seen_ws_tools = set()

            device_label = device_data or (user_choices.get("device_class") if isinstance(user_choices, dict) else "") or "medical device"
            prompt_summary = user_input or "regulatory compliance analysis"

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
                        hint = f"Routing Engine: Parsing user intent, device parameters, and regulatory path for '{prompt_summary[:40]}...'"
                    elif node_name == "classify_node":
                        hint = f"Structured Classifier: Validating regulatory schema and routing compliance for '{prompt_summary[:40]}...'"
                    elif node_name == "device_summary":
                        hint = f"Device Profiler: Synthesizing specifications and classification tier for '{device_label}'..."
                    elif node_name == "knowledge_base":
                        hint = f"Knowledge Base: Performing BM25 + dense retrieval for '{prompt_summary[:40]}...'"
                    elif node_name == "reason_llm":
                        hint = f"Regulatory Expert: Synthesizing compliance pathway and 510(k)/PMA reasoning for '{prompt_summary[:40]}...'"
                    elif node_name == "process_feedback":
                        hint = "Human-in-the-Loop: Awaiting user feedback/authorization on regulatory guidance..."
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
                        t_hint = f"Tool [{tool_name}]: Querying regulatory predicate data for '{str(query_param)[:40]}...'..."
                        await websocket.send_json({"type": "tool_start", "tool": tool_name, "content": t_hint})

                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    t_hint = f"Tool [{tool_name}]: Regulatory intelligence retrieved for '{device_label}'"
                    await websocket.send_json({"type": "tool_end", "tool": tool_name, "content": t_hint})

                # Node Completion Hints
                elif event_type == "on_chain_end" and node_name in graph_nodes and node_name not in seen_ws_end_nodes:
                    seen_ws_end_nodes.add(node_name)
                    if node_name == "classify_node":
                        hint = f"Structured Classifier: Confirmed regulatory classification for '{prompt_summary[:35]}...'"
                    elif node_name == "device_summary":
                        hint = f"Device Profiler: Generated technical profile for '{device_label}'"
                    elif node_name == "knowledge_base":
                        hint = f"Knowledge Base: Matched relevant FDA regulations and guidance documents"
                    elif node_name == "reason_llm":
                        hint = f"Regulatory Expert: Finalized compliance recommendations for '{device_label}'"
                    else:
                        hint = f"Completed {node_name}"

                    await websocket.send_json({"type": "hint", "stage": node_name, "status": "completed", "content": hint})

                # Token streaming ONLY from final RegulatoryExpert node
                elif event_type == "on_chat_model_stream":
                    if any(tag in ["RegulatoryExpert", "reason_llm"] for tag in event_tags):
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
