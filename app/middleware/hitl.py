"""Human In The Loop (HITL) Middleware for Sensitive Tool Interception."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from app.middleware.base import AgentMiddleware

logger = logging.getLogger(__name__)


class HumanApprovalRequiredException(Exception):
    """Raised when an agent attempts to execute a sensitive tool requiring human authorization."""

    def __init__(self, tool_name: str, tool_args: Dict[str, Any], prompt: str = ""):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.prompt = prompt or f"Human approval required before executing sensitive tool '{tool_name}'."
        super().__init__(self.prompt)


class HumanInTheLoopMiddleware(AgentMiddleware):
    """Intercepts sensitive tools (e.g., inventory checks, SQL mutations) and pauses for human approval."""

    name: str = "human_in_the_loop"

    def __init__(
        self,
        sensitive_tools: Optional[List[str]] = None,
        interrupt_on: Optional[Dict[str, bool]] = None,
        raise_exception_on_trigger: bool = False,
    ):
        """
        Initializes HumanInTheLoopMiddleware.

        Args:
            sensitive_tools: List of tool names requiring human approval.
            interrupt_on: Dictionary mapping tool_name -> bool.
            raise_exception_on_trigger: If True, raises HumanApprovalRequiredException instead of setting state flags.
        """
        self.sensitive_tools: Set[str] = set(sensitive_tools or [
            "execute_sql_mutation",
            "modify_database",
            "submit_fda_filing",
            "delete_records",
            "override_inventory",
        ])

        if interrupt_on:
            for tool_name, should_interrupt in interrupt_on.items():
                if should_interrupt:
                    self.sensitive_tools.add(tool_name)
                elif tool_name in self.sensitive_tools:
                    self.sensitive_tools.remove(tool_name)

        self.raise_exception = raise_exception_on_trigger

    def is_sensitive(self, tool_name: str) -> bool:
        """Returns True if the tool requires human approval."""
        return tool_name in self.sensitive_tools

    async def before_tools(
        self,
        state: Dict[str, Any],
        tool_calls: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Intercepts sensitive tool calls prior to execution."""
        if not tool_calls:
            return state, tool_calls

        sensitive_invocations = []
        for call in tool_calls:
            tool_name = call.get("name") or call.get("tool_name") or ""
            if self.is_sensitive(tool_name):
                sensitive_invocations.append(call)

        if sensitive_invocations:
            first = sensitive_invocations[0]
            tool_name = first.get("name") or first.get("tool_name")
            tool_args = first.get("args") or first.get("parameters") or {}

            logger.warning(f"HITL Interceptor triggered for sensitive tool: '{tool_name}' with args: {tool_args}")
            state["human_approval_required"] = True
            state["pending_sensitive_tool"] = {
                "name": tool_name,
                "args": tool_args,
                "requires_approval": True,
            }

            if self.raise_exception:
                raise HumanApprovalRequiredException(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    prompt=f"Action paused: Tool '{tool_name}' requires human auditor approval."
                )

        return state, tool_calls
