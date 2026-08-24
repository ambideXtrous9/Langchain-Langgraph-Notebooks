"""LangGraph SSE Streaming Interaction and Thread Checkpoint Endpoints."""

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import RemoveMessage
from langgraph.types import Command
from app.core.observability import flush_langfuse, get_runnable_config
from app.api.deps import get_current_active_user
from app.schemas.auth import UserResponse
from app.schemas.interact import (
    InteractionRequest,
    DeleteThreadRequest,
    DeleteThreadResponse,
    GraphStateResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def stream_graph_events(
    graph,
    inputs: Any,
    config: Dict[str, Any],
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """Streams events from the LangGraph workflow using Server-Sent Events (SSE).

    1. Yields the thread_id as the initial event.
    2. Emits dynamic node and tool execution hints specialized to user input.
    3. Streams token chunks in real-time ONLY from the final 'RegulatoryExpert' reasoning node.
    4. Handles fallback replies for non-reasoning paths.
    """
    reply_flag = False
    seen_start_nodes = set()
    seen_end_nodes = set()
    seen_tools = set()

    # Extract user input context for dynamic specialized hints
    user_input = ""
    device_name = ""
    if isinstance(inputs, dict):
        user_input = inputs.get("feedback") or ""
        device_name = inputs.get("userProvidedDeiveceData") or inputs.get("user_choices", {}).get("device_class", "") or "medical device"
    elif hasattr(inputs, "resume"):
        user_input = str(inputs.resume)
        device_name = "medical device"

    if not user_input:
        user_input = "regulatory inquiry"

    # 1. Send the thread_id as the initial event
    yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
    logger.info(f"--- Starting Graph Stream for Thread ID: {thread_id} ---")

    graph_nodes = {
        "user_initpath",
        "classify_node",
        "device_summary",
        "knowledge_base",
        "reason_llm",
        "process_feedback",
    }

    try:
        # 2. Stream events from graph execution (v2 event stream protocol)
        events = graph.astream_events(input=inputs, config=config, version="v2")

        async for event in events:
            event_type = event.get("event")
            event_tags = event.get("tags") or []
            node_name = event.get("name", "")

            # 2a. Dynamic Node Start Hints tailored to user input & device context
            if event_type == "on_chain_start" and node_name in graph_nodes and node_name not in seen_start_nodes:
                seen_start_nodes.add(node_name)
                if node_name == "user_initpath":
                    hint = f"Routing Engine: Parsing user intent, device parameters, and regulatory path for '{user_input[:40]}...'"
                elif node_name == "classify_node":
                    hint = f"Structured Classifier: Validating regulatory schema and routing compliance for '{user_input[:40]}...'"
                elif node_name == "device_summary":
                    hint = f"Device Profiler: Synthesizing specifications and classification tier for '{device_name}'..."
                elif node_name == "knowledge_base":
                    hint = f"Knowledge Base: Performing BM25 + dense retrieval for '{user_input[:40]}...'"
                elif node_name == "reason_llm":
                    hint = f"Regulatory Expert: Synthesizing compliance pathway and 510(k)/PMA reasoning for '{user_input[:40]}...'"
                elif node_name == "process_feedback":
                    hint = "Human-in-the-Loop: Awaiting user feedback/authorization on regulatory guidance..."
                else:
                    hint = f"Executing Node: {node_name} for '{user_input[:35]}...'"

                yield f"data: {json.dumps({'stage': node_name, 'status': 'started', 'hint': hint})}\n\n"

            # 2b. Dynamic Tool Execution Start Hints
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("data", {}).get("input") or {}
                tool_run_id = event.get("run_id", tool_name)

                if tool_run_id not in seen_tools:
                    seen_tools.add(tool_run_id)
                    query_param = ""
                    if isinstance(tool_input, dict):
                        query_param = tool_input.get("query") or tool_input.get("q") or str(tool_input)
                    else:
                        query_param = str(tool_input)

                    tool_hint = f"Tool [{tool_name}]: Querying regulatory predicate data for '{query_param[:40]}...'..."
                    yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # 2c. Dynamic Tool Execution End Hints
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "tool")
                tool_hint = f"Tool [{tool_name}]: Regulatory intelligence retrieved for '{device_name}'"
                yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # 2d. Dynamic Node Completion Hints
            elif event_type == "on_chain_end" and node_name in graph_nodes and node_name not in seen_end_nodes:
                seen_end_nodes.add(node_name)
                output = event.get("data", {}).get("output") or {}

                if node_name == "classify_node":
                    cls_val = output.get("classification", {})
                    choice_str = cls_val.get("user_choice") or cls_val.get("decision_path") or "analyzed"
                    hint = f"Structured Classifier: Confirmed route '{choice_str}' for '{user_input[:35]}...'"
                elif node_name == "device_summary":
                    hint = f"Device Profiler: Generated technical profile for '{device_name}'"
                elif node_name == "knowledge_base":
                    hint = f"Knowledge Base: Matched relevant FDA regulations and guidance documents"
                elif node_name == "reason_llm":
                    hint = f"Regulatory Expert: Finalized compliance recommendations for '{device_name}'"
                else:
                    hint = f"Completed {node_name} for '{user_input[:35]}...'"

                yield f"data: {json.dumps({'stage': node_name, 'status': 'completed', 'hint': hint})}\n\n"

            # 3. Stream tokens ONLY from the final reasoning LLM node
            elif event_type == "on_chat_model_stream":
                if any(tag in ["RegulatoryExpert", "reason_llm"] for tag in event_tags):
                    chunk = event.get("data", {}).get("chunk")
                    chunk_content = getattr(chunk, "content", "") if chunk else ""
                    if chunk_content:
                        reply_flag = True
                        yield f"data: {json.dumps({'response': chunk_content})}\n\n"

        # 4. Fallback for generic or classified replies if reasoning node was bypassed
        if not reply_flag:
            current_state = await graph.aget_state(config)
            classification = current_state.values.get("classification", {})
            if isinstance(classification, dict) and classification.get("reply"):
                yield f"data: {json.dumps({'response': classification['reply']})}\n\n"
            elif current_state.values.get("chat_history"):
                last_msg = current_state.values["chat_history"][-1]
                content = getattr(last_msg, "content", str(last_msg))
                yield f"data: {json.dumps({'response': content})}\n\n"

    except Exception as e:
        logger.error(f"Exception during graph streaming for thread {thread_id}: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        flush_langfuse()
        logger.info(f"--- Finished Graph Stream for Thread ID: {thread_id} ---")


@router.post("/interact", tags=["Interaction"])
async def interact_endpoint(
    request: InteractionRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Executes the graph workflow and streams token responses in real-time via SSE."""
    graph = getattr(req.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph execution engine is not initialized.",
        )

    # Validate input
    is_empty_choices = not request.user_choices or request.user_choices == {}
    is_empty_input = not request.user_input or str(request.user_input).strip() == ""

    if is_empty_choices and is_empty_input:

        async def stream_empty_input_message():
            yield f"data: {json.dumps({'response': 'No input provided. Please enter a choice or input text.'})}\n\n"

        return StreamingResponse(stream_empty_input_message(), media_type="text/event-stream")

    thread_id = request.thread_id or f"user-{current_user.id}-{uuid.uuid4()}"
    thread_config = get_runnable_config(
        thread_id=thread_id,
        metadata={"user_id": current_user.id, "email": current_user.email},
    )

    if not request.thread_id:
        # 1. Start a new graph conversation
        initial_state = {
            "user_choices": request.user_choices or {},
            "feedback": request.user_input or "",
            "useDeviceData": request.useDeviceData,
            "userProvidedDeiveceData": request.userProvidedDeiveceData or "",
            "chat_history": [],
        }
        return StreamingResponse(
            stream_graph_events(graph, initial_state, thread_config, thread_id),
            media_type="text/event-stream",
        )
    else:
        # 2. Continue existing graph conversation / Resume from interrupt
        current_state = await graph.aget_state(thread_config)

        # Check if the thread exists and is already completed
        if not current_state or not current_state.next:

            async def stream_completion_message():
                yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
                yield f"data: {json.dumps({'response': 'Graph execution is complete for this session.'})}\n\n"

            return StreamingResponse(stream_completion_message(), media_type="text/event-stream")

        # Resume suspended interrupt node with user input and state update
        inputs = Command(
            resume=request.user_input,
            update={
                "useDeviceData": request.useDeviceData,
                "userProvidedDeiveceData": request.userProvidedDeiveceData or "",
            },
        )
        return StreamingResponse(
            stream_graph_events(graph, inputs, thread_config, thread_id),
            media_type="text/event-stream",
        )


@router.get("/thread/{thread_id}/state", response_model=GraphStateResponse, tags=["Interaction"])
async def get_thread_state(
    thread_id: str,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Retrieves the live state and next active nodes for a given thread checkpoint."""
    graph = getattr(req.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph execution engine is not initialized.",
        )

    thread_config = get_runnable_config(thread_id=thread_id)
    current_state = await graph.aget_state(thread_config)

    if not current_state or not current_state.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active state found for thread_id '{thread_id}'",
        )

    return GraphStateResponse(
        thread_id=thread_id,
        next_nodes=list(current_state.next) if current_state.next else [],
        values=current_state.values,
        is_completed=not bool(current_state.next),
    )


@router.delete("/delete_thread", response_model=DeleteThreadResponse, tags=["Interaction"])
async def delete_thread_endpoint(
    request: DeleteThreadRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Deletes all checkpoints and history for a given thread_id from PostgreSQL checkpointer."""
    try:
        checkpointer = getattr(req.app.state, "checkpointer", None)
        if not checkpointer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Checkpointer is not initialized.",
            )

        thread_config = get_runnable_config(thread_id=request.thread_id)

        # Check if the thread exists
        if hasattr(checkpointer, "aget"):
            thread_exists = await checkpointer.aget(thread_config)
            if not thread_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Thread '{request.thread_id}' not found in checkpointer.",
                )

        # Delete thread if supported by checkpointer
        if hasattr(checkpointer, "adelete_thread"):
            await checkpointer.adelete_thread(request.thread_id)
        elif hasattr(checkpointer, "delete_thread"):
            checkpointer.delete_thread(request.thread_id)

        return DeleteThreadResponse(
            message="Thread deleted successfully",
            thread_id=request.thread_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting thread checkpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete thread: {str(e)}",
        )
