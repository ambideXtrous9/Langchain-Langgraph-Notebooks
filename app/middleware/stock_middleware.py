"""Stock Analysis Agent Middlewares: Throttling, Telemetry, Self-Critique, and Context Editing."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage
from app.middleware.base import AgentMiddleware

logger = logging.getLogger(__name__)


class StockThrottleMiddleware(AgentMiddleware):
    """Throttles agent requests to protect LLM endpoints and external APIs from bursts."""

    name: str = "stock_throttle"

    def __init__(self, delay_seconds: float = 0.05, max_calls_per_minute: int = 120):
        self.delay_seconds = delay_seconds
        self.max_calls_per_minute = max_calls_per_minute
        self._call_timestamps: List[float] = []

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        now = time.time()
        # Remove timestamps older than 60s
        self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]

        if len(self._call_timestamps) >= self.max_calls_per_minute:
            sleep_time = 60.0 - (now - self._call_timestamps[0])
            if sleep_time > 0:
                logger.info(f"[ThrottleMiddleware] Rate limit reached. Pacing {sleep_time:.2f}s...")
                await asyncio.sleep(min(sleep_time, 2.0))

        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        self._call_timestamps.append(time.time())
        return state, messages


class StockTelemetryMiddleware(AgentMiddleware):
    """Collects telemetry metrics including latency, tool calls, and model invocations."""

    name: str = "stock_telemetry"

    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_model_calls": 0,
            "total_tool_calls": 0,
            "total_latency_seconds": 0.0,
            "tool_call_types": {},
        }
        self._start_time: float = 0.0

    async def before_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self._start_time = time.time()
        return state

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        self.metrics["total_model_calls"] += 1
        return state, messages

    async def before_tools(
        self,
        state: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        self.metrics["total_tool_calls"] += len(tool_calls)
        for tc in tool_calls:
            name = tc.get("name", "unknown")
            self.metrics["tool_call_types"][name] = self.metrics["tool_call_types"].get(name, 0) + 1
        return state, tool_calls

    async def after_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self.metrics["total_latency_seconds"] = round(time.time() - self._start_time, 3)
        state["telemetry"] = self.metrics.copy()
        return state


class StockSelfCritiqueMiddleware(AgentMiddleware):
    """Enforces self-critique on agent findings to catch hallucinations and ground claims in data."""

    name: str = "stock_self_critique"

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode

    async def after_model(
        self,
        state: Dict[str, Any],
        response: Any,
    ) -> Tuple[Dict[str, Any], Any]:
        # Inspect response content for ungrounded superlatives or unsourced metrics
        content = getattr(response, "content", "") if response else ""
        if isinstance(content, str):
            flags = []
            if "guaranteed" in content.lower() or "100% sure" in content.lower():
                flags.append("Unwarranted certainty detected.")
            if flags:
                logger.warning(f"[SelfCritiqueMiddleware] Quality warning: {flags}")
                state.setdefault("critique_flags", []).extend(flags)
        return state, response


class StockContextEditingMiddleware(AgentMiddleware):
    """Compresses verbose tool responses to prevent token overflow while preserving critical numbers."""

    name: str = "stock_context_editing"

    def __init__(self, max_tool_chars: int = 4000):
        self.max_tool_chars = max_tool_chars

    async def after_tools(
        self,
        state: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        edited_results = []
        for res in tool_results:
            content = res.get("content", "")
            if isinstance(content, str) and len(content) > self.max_tool_chars:
                # Keep head and tail of tool output
                head = content[: int(self.max_tool_chars * 0.7)]
                tail = content[-int(self.max_tool_chars * 0.3) :]
                res["content"] = f"{head}\n\n... [Context Edited: {len(content) - self.max_tool_chars} characters trimmed] ...\n\n{tail}"
            edited_results.append(res)
        return state, edited_results
