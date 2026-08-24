"""Research Endpoints for the Parallel Research, Critic, and Publisher Architecture."""

import json
import logging
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.core.observability import flush_langfuse, get_runnable_config
from app.schemas.research import ResearchRequest, ResearchResponse

logger = logging.getLogger(__name__)
router = APIRouter()


async def stream_research_events(
    graph,
    inputs: dict,
    config: dict,
    thread_id: str,
) -> AsyncGenerator[str, None]:
    """Streams SSE events from the Parallel Research Graph execution.

    1. Yields thread_id on initiation.
    2. Emits stage progress events with concise, topic-tailored hints.
    3. Streams real-time tokens ONLY from the final `publisher` node.
    4. Emits a clean completion event when done.
    """
    topic = inputs.get("topic", "Research Subject")

    # 1. First event: send thread_id
    yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
    logger.info(f"--- Starting Parallel Research Stream for Thread: {thread_id} ---")

    seen_start_stages = set()
    seen_end_stages = set()
    tokens_streamed = False

    graph_nodes = {
        "planner",
        "approver",
        "researcher_dispatcher",
        "researcher",
        "synthesizer",
        "fact_critic",
        "style_critic_1",
        "style_critic_2",
        "publisher",
    }

    try:
        events = graph.astream_events(input=inputs, config=config, version="v2")

        async for event in events:
            event_type = event.get("event")
            event_tags = event.get("tags") or []
            node_name = event.get("name", "")

            # 2a. Dynamic Start Hint tailored to user input topic
            if event_type == "on_chain_start" and node_name in graph_nodes and node_name not in seen_start_stages:
                seen_start_stages.add(node_name)
                start_hint = f"Executing {node_name.replace('_', ' ').title()} for: '{topic[:50]}...'"
                yield f"data: {json.dumps({'stage': node_name, 'status': 'started', 'hint': start_hint})}\n\n"

            # 2b. Dynamic Node-Generated Completion Hint with actual findings/metrics
            elif event_type == "on_chain_end" and node_name in graph_nodes and node_name not in seen_end_stages:
                seen_end_stages.add(node_name)
                output = event.get("data", {}).get("output") or {}

                if node_name == "planner":
                    q_count = len(output.get("research_queries", []))
                    hint_msg = f"Drafted strategic research plan with {q_count} search queries for '{topic[:45]}...'"
                elif node_name == "approver":
                    is_app = output.get("plan_approved", True)
                    hint_msg = f"Approver Agent: {'Approved plan' if is_app else 'Revision requested'} for '{topic[:40]}...'"
                elif node_name == "researcher_dispatcher":
                    queries = output.get("research_queries", [])
                    hint_msg = f"Dispatched {len(queries)} search queries for '{topic[:40]}...'"
                elif node_name == "researcher":
                    notes = output.get("research_notes", [])
                    hint_msg = f"Retrieved {len(notes)} live DuckDuckGo intelligence briefs on '{topic[:40]}...'"
                elif node_name == "synthesizer":
                    words = len(output.get("draft", "").split())
                    hint_msg = f"Synthesized initial {words}-word report draft for '{topic[:40]}...'"
                elif node_name == "fact_critic":
                    hint_msg = f"Fact Critic audited regulatory claims and source citations for '{topic[:40]}...'"
                elif node_name == "style_critic_1":
                    hint_msg = f"Style Critic 1 optimized narrative clarity and voice for '{topic[:40]}...'"
                elif node_name == "style_critic_2":
                    hint_msg = f"Style Critic 2 refined executive layout, summary tables and takeaways for '{topic[:40]}...'"
                elif node_name == "publisher":
                    hint_msg = f"Publisher merged all critiques (defer=True) into final publication for '{topic[:40]}...'"
                else:
                    hint_msg = f"Completed {node_name} for '{topic[:45]}...'"

                yield f"data: {json.dumps({'stage': node_name, 'status': 'completed', 'hint': hint_msg})}\n\n"

            # 2c. Dynamic Tool Execution Start Hints (specialized with query parameters)
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("data", {}).get("input") or {}
                query_param = ""
                if isinstance(tool_input, dict):
                    query_param = tool_input.get("query") or tool_input.get("q") or tool_input.get("search_query") or ""
                elif isinstance(tool_input, str):
                    query_param = tool_input

                query_disp = f" for '{query_param[:45]}...'" if query_param else f" for topic '{topic[:35]}...'"
                tool_hint = f"Web Intelligence Tool [{tool_name}]: Searching live regulatory briefings{query_disp}..."
                yield f"data: {json.dumps({'event': 'tool_start', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # 2d. Dynamic Tool Execution End Hints
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "tool")
                tool_hint = f"Web Intelligence Tool [{tool_name}]: Live briefs retrieved for '{topic[:35]}...'"
                yield f"data: {json.dumps({'event': 'tool_end', 'tool': tool_name, 'data': tool_hint})}\n\n"

            # 3. Stream tokens ONLY from the final publisher node
            elif event_type == "on_chat_model_stream":
                if any(tag in ["Publisher", "ResearchPublisher"] for tag in event_tags):
                    chunk = event.get("data", {}).get("chunk")
                    chunk_content = getattr(chunk, "content", "") if chunk else ""
                    if chunk_content:
                        tokens_streamed = True
                        yield f"data: {json.dumps({'token': chunk_content})}\n\n"

        # 4. Fallback if tokens were not streamed directly
        if not tokens_streamed:
            final_state = await graph.aget_state(config)
            published = final_state.values.get("final_output", "")
            if published:
                yield f"data: {json.dumps({'token': published})}\n\n"

        # 5. Emit clean completion event and standard SSE termination signal
        yield f"data: {json.dumps({'status': 'completed', 'stage': 'publisher', 'message': 'Research publication complete'})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error streaming research graph for thread {thread_id}: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        flush_langfuse()
        logger.info(f"--- Completed Parallel Research Stream for Thread: {thread_id} ---")


from app.api.deps import get_current_active_user
from app.schemas.auth import UserResponse

@router.post("/research/run", response_model=ResearchResponse, tags=["Research Pipeline"])
async def run_research_endpoint(
    request: ResearchRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Executes the complete parallel research graph synchronously."""
    research_graph = getattr(req.app.state, "research_graph", None)
    if research_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research Graph execution engine is not initialized.",
        )

    thread_id = request.thread_id or f"user-{current_user.id}-{uuid.uuid4()}"
    run_config = get_runnable_config(
        thread_id=thread_id,
        tags=["research_pipeline", "parallel_execution", "defer_publisher"],
        metadata={"topic": request.topic, "user_id": current_user.id, "email": current_user.email},
    )

    initial_input = {
        "topic": request.topic,
        "plan": "",
        "plan_critique": "",
        "plan_approved": False,
        "plan_revision_count": 0,
        "research_queries": [],
        "research_notes": [],
        "draft": "",
        "fact_critique": "",
        "style_critique_1": "",
        "style_critique_2": "",
        "final_output": "",
        "messages": [],
    }

    try:
        final_state = await research_graph.ainvoke(initial_input, config=run_config)
        flush_langfuse()

        return ResearchResponse(
            topic=request.topic,
            plan=final_state.get("plan", ""),
            plan_approved=final_state.get("plan_approved", True),
            draft=final_state.get("draft", ""),
            fact_critique=final_state.get("fact_critique", ""),
            style_critique_1=final_state.get("style_critique_1", ""),
            style_critique_2=final_state.get("style_critique_2", ""),
            final_output=final_state.get("final_output", ""),
            research_notes_count=len(final_state.get("research_notes", [])),
        )

    except Exception as e:
        logger.error(f"Failed to execute research pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research execution failed: {str(e)}",
        )


@router.post("/research/stream", tags=["Research Pipeline"])
async def stream_research_endpoint(
    request: ResearchRequest,
    req: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Initiates Server-Sent Events (SSE) streaming for the parallel research graph."""
    research_graph = getattr(req.app.state, "research_graph", None)
    if research_graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Research Graph execution engine is not initialized.",
        )

    thread_id = request.thread_id or f"user-{current_user.id}-{uuid.uuid4()}"
    run_config = get_runnable_config(
        thread_id=thread_id,
        tags=["research_stream", "parallel_execution", "defer_publisher"],
        metadata={"topic": request.topic, "user_id": current_user.id, "email": current_user.email},
    )

    initial_input = {
        "topic": request.topic,
        "plan": "",
        "plan_critique": "",
        "plan_approved": False,
        "plan_revision_count": 0,
        "research_queries": [],
        "research_notes": [],
        "draft": "",
        "fact_critique": "",
        "style_critique_1": "",
        "style_critique_2": "",
        "final_output": "",
        "messages": [],
    }

    return StreamingResponse(
        stream_research_events(
            graph=research_graph,
            inputs=initial_input,
            config=run_config,
            thread_id=thread_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research/mermaid", response_class=PlainTextResponse, tags=["Research Pipeline"])
async def get_research_mermaid_endpoint(req: Request) -> str:
    """Returns the Mermaid diagram representation of the active Parallel Research Graph."""
    research_graph = getattr(req.app.state, "research_graph", None)
    if research_graph:
        return research_graph.get_graph().draw_mermaid()
    return "Research Graph not initialized yet."
