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
            events = graph.astream_events(input=graph_input, config=thread_config, version="v2")

            async for event in events:
                event_type = event.get("event")
                event_tags = event.get("tags") or []

                if event_type == "on_chat_model_stream":
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
