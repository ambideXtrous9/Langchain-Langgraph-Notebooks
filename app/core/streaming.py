"""Unified Streaming Engine for Server-Sent Events (SSE) and WebSocket streams."""

import json
import logging
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Set
from app.core.observability import flush_langfuse

logger = logging.getLogger(__name__)


def format_sse(data: Dict[str, Any], event: Optional[str] = None) -> str:
    """Formats a payload dictionary into standard SSE wire protocol."""
    payload = json.dumps(data)
    if event:
        return f"event: {event}\ndata: {payload}\n\n"
    return f"data: {payload}\n\n"


def extract_token_text(chunk: Any) -> str:
    """Safely extracts plain text content from a streaming LLM token chunk."""
    if not chunk:
        return ""
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


async def stream_graph_sse(
    graph: Any,
    inputs: Any,
    config: Dict[str, Any],
    stream_tags: Set[str],
    graph_nodes: Optional[Set[str]] = None,
    initial_event: Optional[Dict[str, Any]] = None,
    node_start_hint: Optional[Callable[[str], Optional[str]]] = None,
    node_end_hint: Optional[Callable[[str, Dict[str, Any]], Optional[str]]] = None,
    tool_start_hint: Optional[Callable[[str, Any], Optional[str]]] = None,
    tool_end_hint: Optional[Callable[[str, Any], Optional[str]]] = None,
    fallback_resolver: Optional[Callable[[], Any]] = None,
    stream_format: str = "interact",  # "interact" | "mcp"
    target_agent_name: str = "agent",
    completion_message: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Unified generator streaming LangGraph execution events via Server-Sent Events (SSE).

    Handles:
    - Initial event dispatch (e.g. thread_id acknowledgment).
    - Lifecycle hints for node start/end and tool start/end.
    - Tag-filtered token chunk streaming.
    - Fallback content extraction when LLM streaming was bypassed.
    - Centralized exception logging and Langfuse trace flushing.
    """
    seen_start_nodes: Set[str] = set()
    seen_end_nodes: Set[str] = set()
    seen_tools: Set[str] = set()
    tokens_streamed = False
    last_summary = ""

    if initial_event:
        yield format_sse(initial_event)

    try:
        try:
            if config:
                events = graph.astream_events(inputs, config=config, version="v2")
            else:
                events = graph.astream_events(inputs, version="v2")
        except TypeError:
            events = graph.astream_events(input=inputs, config=config, version="v2")

        async for event in events:
            event_type = event.get("event")
            event_tags = event.get("tags") or []
            metadata = event.get("metadata", {})
            node_name = event.get("name", "") or metadata.get("langgraph_node", "")

            # 1. Node Start Hints
            if event_type in ["on_chain_start", "on_chat_model_start"] and graph_nodes and node_name in graph_nodes and node_name not in seen_start_nodes:
                seen_start_nodes.add(node_name)
                hint = node_start_hint(node_name) if node_start_hint else f"Executing {node_name}..."
                if hint:
                    if stream_format == "mcp":
                        yield format_sse({"event": "hint", "agent": node_name, "data": hint})
                    else:
                        yield format_sse({"stage": node_name, "status": "started", "hint": hint})

            # 2. Tool Execution Start Hints
            elif event_type == "on_tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("data", {}).get("input") or {}
                tool_id = event.get("run_id", tool_name)

                if tool_id not in seen_tools:
                    seen_tools.add(tool_id)
                    hint = tool_start_hint(tool_name, tool_input) if tool_start_hint else f"Tool [{tool_name}]: Running..."
                    if hint:
                        yield format_sse({"event": "tool_start", "tool": tool_name, "data": hint})

            # 3. Tool Execution End Hints
            elif event_type == "on_tool_end":
                tool_name = event.get("name", "tool")
                tool_output = event.get("data", {}).get("output") or {}
                hint = tool_end_hint(tool_name, tool_output) if tool_end_hint else f"Tool [{tool_name}]: Finished."
                if hint:
                    yield format_sse({"event": "tool_end", "tool": tool_name, "data": hint})

            # 4. Node Completion Hints
            elif event_type == "on_chain_end" and graph_nodes and node_name in graph_nodes and node_name not in seen_end_nodes:
                seen_end_nodes.add(node_name)
                output = event.get("data", {}).get("output") or {}
                if isinstance(output, dict) and "summary" in output:
                    last_summary = output["summary"]

                hint = node_end_hint(node_name, output) if node_end_hint else f"Completed {node_name}."
                if hint:
                    if stream_format == "mcp":
                        yield format_sse({"event": "hint", "agent": node_name, "data": hint})
                    else:
                        yield format_sse({"stage": node_name, "status": "completed", "hint": hint})

            # 5. Token Streaming
            elif event_type == "on_chat_model_stream":
                if any(tag in stream_tags for tag in event_tags):
                    chunk = event.get("data", {}).get("chunk")
                    token_text = extract_token_text(chunk)
                    if token_text:
                        tokens_streamed = True
                        if stream_format == "mcp":
                            yield format_sse({"event": "token", "agent": target_agent_name, "data": token_text})
                        else:
                            yield format_sse({"response": token_text})

        # 6. Fallback if tokens were bypassed
        if not tokens_streamed:
            if last_summary and stream_format == "mcp":
                yield format_sse({"event": "token", "agent": target_agent_name, "data": last_summary})
            elif fallback_resolver:
                fallback_msg = await fallback_resolver() if callable(fallback_resolver) else str(fallback_resolver)
                if fallback_msg:
                    if stream_format == "mcp":
                        yield format_sse({"event": "token", "agent": target_agent_name, "data": fallback_msg})
                    else:
                        yield format_sse({"response": fallback_msg})

        # 7. Optional completion message
        if completion_message:
            yield format_sse({"event": "done", "data": completion_message})

    except Exception as exc:
        logger.error(f"Streaming exception: {exc}", exc_info=True)
        if stream_format == "mcp":
            yield format_sse({"event": "error", "data": str(exc)})
        else:
            yield format_sse({"error": str(exc)})
    finally:
        flush_langfuse()
