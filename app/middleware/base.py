"""Base Agent Middleware Architecture and Pipeline Executor."""

import abc
import logging
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


class AgentMiddleware(abc.ABC):
    """Abstract Base Class for Agent Middlewares in LangGraph and Agent Pipelines."""

    name: str = "base_middleware"

    async def before_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before agent workflow starts."""
        return state

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        """Hook executed immediately before invoking the LLM."""
        return state, messages

    async def after_model(
        self,
        state: Dict[str, Any],
        response: Any,
    ) -> Tuple[Dict[str, Any], Any]:
        """Hook executed immediately after receiving LLM completion."""
        return state, response

    async def before_tools(
        self,
        state: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Hook executed before executing tool calls."""
        return state, tool_calls

    async def after_tools(
        self,
        state: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Hook executed after tools have finished execution."""
        return state, tool_results

    async def after_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed at the very end of agent execution."""
        return state


class AgentMiddlewarePipeline:
    """Executes an ordered pipeline of AgentMiddlewares across lifecycle hooks."""

    def __init__(self, middlewares: Optional[List[AgentMiddleware]] = None):
        self.middlewares: List[AgentMiddleware] = middlewares or []

    def add_middleware(self, middleware: AgentMiddleware) -> None:
        """Appends a middleware to the pipeline."""
        self.middlewares.append(middleware)

    async def run_before_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs before_agent hook across all middlewares in order."""
        current_state = state
        for mw in self.middlewares:
            current_state = await mw.before_agent(current_state)
        return current_state

    async def run_before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        """Runs before_model hook across all middlewares in order."""
        current_state = state
        current_messages = messages
        for mw in self.middlewares:
            current_state, current_messages = await mw.before_model(current_state, current_messages)
        return current_state, current_messages

    async def run_after_model(
        self,
        state: Dict[str, Any],
        response: Any,
    ) -> Tuple[Dict[str, Any], Any]:
        """Runs after_model hook across all middlewares in order."""
        current_state = state
        current_response = response
        for mw in self.middlewares:
            current_state, current_response = await mw.after_model(current_state, current_response)
        return current_state, current_response

    async def run_before_tools(
        self,
        state: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Runs before_tools hook across all middlewares in order."""
        current_state = state
        current_tools = tool_calls
        for mw in self.middlewares:
            current_state, current_tools = await mw.before_tools(current_state, current_tools)
        return current_state, current_tools

    async def run_after_tools(
        self,
        state: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Runs after_tools hook across all middlewares in order."""
        current_state = state
        current_results = tool_results
        for mw in self.middlewares:
            current_state, current_results = await mw.after_tools(current_state, current_results)
        return current_state, current_results

    async def run_after_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs after_agent hook across all middlewares in order."""
        current_state = state
        for mw in self.middlewares:
            current_state = await mw.after_agent(current_state)
        return current_state
