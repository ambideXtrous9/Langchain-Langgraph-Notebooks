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
from app.core.streaming import stream_graph_sse
from app.api.deps import get_current_active_user
from app.schemas.auth import UserResponse
from app.schemas.state import get_device_data
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
    """Streams events from the LangGraph workflow using Server-Sent Events (SSE)."""
    user_input = ""
    device_name = ""
    if isinstance(inputs, dict):
        user_input = inputs.get("feedback") or ""
        device_name = get_device_data(inputs) or inputs.get("user_choices", {}).get("device_class", "") or "medical device"
    elif hasattr(inputs, "resume"):
        user_input = str(inputs.resume)
        device_name = "medical device"

    if not user_input:
        user_input = "regulatory inquiry"

    logger.info(f"--- Starting Graph Stream for Thread ID: {thread_id} ---")

    graph_nodes = {
        "user_initpath",
        "classify_node",
        "device_summary",
        "knowledge_base",
        "reason_llm",
        "process_feedback",
    }

    def node_start_hint(node_name: str) -> str:
        if node_name == "user_initpath":
            return f"Routing Engine: Parsing user intent, device parameters, and regulatory path for '{user_input[:40]}...'"
        elif node_name == "classify_node":
            return f"Structured Classifier: Validating regulatory schema and routing compliance for '{user_input[:40]}...'"
        elif node_name == "device_summary":
            return f"Device Profiler: Synthesizing specifications and classification tier for '{device_name}'..."
        elif node_name == "knowledge_base":
            return f"Knowledge Base: Performing BM25 + dense retrieval for '{user_input[:40]}...'"
        elif node_name == "reason_llm":
            return f"Regulatory Expert: Synthesizing compliance pathway and 510(k)/PMA reasoning for '{user_input[:40]}...'"
        elif node_name == "process_feedback":
            return "Human-in-the-Loop: Awaiting user feedback/authorization on regulatory guidance..."
        return f"Executing Node: {node_name} for '{user_input[:35]}...'"

    def node_end_hint(node_name: str, output: Dict[str, Any]) -> str:
        if node_name == "classify_node":
            cls_val = output.get("classification", {})
            choice_str = cls_val.get("user_choice") or cls_val.get("decision_path") or "analyzed"
            return f"Structured Classifier: Confirmed route '{choice_str}' for '{user_input[:35]}...'"
        elif node_name == "device_summary":
            return f"Device Profiler: Generated technical profile for '{device_name}'"
        elif node_name == "knowledge_base":
            return "Knowledge Base: Matched relevant FDA regulations and guidance documents"
        elif node_name == "reason_llm":
            return f"Regulatory Expert: Finalized compliance recommendations for '{device_name}'"
        return f"Completed {node_name} for '{user_input[:35]}...'"

    def tool_start_hint(tool_name: str, tool_input: Any) -> str:
        query_param = (
            tool_input.get("query") or tool_input.get("q") or str(tool_input)
            if isinstance(tool_input, dict)
            else str(tool_input)
        )
        return f"Tool [{tool_name}]: Querying regulatory predicate data for '{query_param[:40]}...'..."

    def tool_end_hint(tool_name: str, tool_output: Any) -> str:
        return f"Tool [{tool_name}]: Regulatory intelligence retrieved for '{device_name}'"

    async def fallback_resolver():
        current_state = await graph.aget_state(config)
        if not current_state:
            return ""
        classification = current_state.values.get("classification", {})
        if isinstance(classification, dict) and classification.get("reply"):
            return classification["reply"]
        elif current_state.values.get("chat_history"):
            last_msg = current_state.values["chat_history"][-1]
            return getattr(last_msg, "content", str(last_msg))
        return ""

    async for chunk in stream_graph_sse(
        graph=graph,
        inputs=inputs,
        config=config,
        stream_tags={"RegulatoryExpert", "reason_llm"},
        graph_nodes=graph_nodes,
        initial_event={"thread_id": thread_id},
        node_start_hint=node_start_hint,
        node_end_hint=node_end_hint,
        tool_start_hint=tool_start_hint,
        tool_end_hint=tool_end_hint,
        fallback_resolver=fallback_resolver,
        stream_format="interact",
    ):
        yield chunk

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
            "userProvidedDeiveceData": request.device_data,
            "user_provided_device_data": request.device_data,
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
                "userProvidedDeiveceData": request.device_data,
                "user_provided_device_data": request.device_data,
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

        # 1. Delete thread from checkpointer instance
        if hasattr(checkpointer, "adelete_thread"):
            try:
                await checkpointer.adelete_thread(request.thread_id)
            except Exception as e:
                logger.warning(f"checkpointer.adelete_thread error: {e}")
        elif hasattr(checkpointer, "delete_thread"):
            try:
                checkpointer.delete_thread(request.thread_id)
            except Exception as e:
                logger.warning(f"checkpointer.delete_thread error: {e}")

        # 2. Directly purge PostgreSQL checkpoint tables for guaranteed removal
        db_pool = getattr(req.app.state, "db_pool", None)
        if db_pool:
            try:
                async with db_pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            DELETE FROM checkpoint_writes WHERE thread_id = %s;
                            DELETE FROM checkpoint_blobs WHERE thread_id = %s;
                            DELETE FROM checkpoints WHERE thread_id = %s;
                            """,
                            (request.thread_id, request.thread_id, request.thread_id),
                        )
                        logger.info(f"Purged checkpoints for thread '{request.thread_id}' from PostgreSQL.")
            except Exception as pool_err:
                logger.warning(f"Direct PostgreSQL checkpoint tables deletion warning: {pool_err}")

        return DeleteThreadResponse(
            message="Thread and PostgreSQL checkpoints deleted successfully",
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
