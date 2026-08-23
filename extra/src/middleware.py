import functools
from typing import Callable, Any
from langchain.agents.middleware import (
    PIIMiddleware,
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
    AgentMiddleware
)
from langchain_core.messages import AIMessage
from langsmith import traceable
from .models import ProdAgentState
from .config import summarizer_llm

# 6. Middleware Layers: Guardrails + Memory
email_pii_guard = PIIMiddleware(
    pii_type="email",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=True
)

hil_guard = HumanInTheLoopMiddleware(
    interrupt_on={"get_inventory": True}  # Review stock checks
)

summarizer = SummarizationMiddleware(
    model=summarizer_llm, # Pass the LLM instance
    trigger=("tokens", 4000),    # Auto-condense long convos
    summary_key="session_summary"
)

# Define the custom middleware class to wrap the rate_limit_guard function
class CustomRateLimitMiddleware(AgentMiddleware):
    def __init__(self, rate_limit_func: Callable[[ProdAgentState], ProdAgentState]):
        self._rate_limit_func = rate_limit_func

    # Implement all abstract methods as required by AgentMiddleware
    def wrap_tool_call(self, tool_request: Any, execute_tool: Callable[..., Any], extra_arg: Any = None) -> Any:
        # Pass the tool_request to the execute_tool callable, along with any extra arguments
        if extra_arg is not None:
            return execute_tool(tool_request, extra_arg)
        return execute_tool(tool_request)

    async def awrap_tool_call(self, tool_request: Any, execute_tool: Callable[..., Any], extra_arg: Any = None) -> Any:
        # Pass the tool_request to the execute_tool callable, along with any extra arguments
        if extra_arg is not None:
            return await execute_tool(tool_request, extra_arg)
        return await execute_tool(tool_request)

    def wrap_run(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(state: ProdAgentState, *args, **kwargs) -> ProdAgentState:
            # Apply the rate_limit_func to the state before the main run
            processed_state = self._rate_limit_func(state)

            # If the rate limit logic decided to terminate early, return that state
            if processed_state.get("messages") and processed_state["messages"][-1].content == "Rate limited. Try again in 5min.":
                return processed_state

            # Otherwise, proceed with the original agent run function
            # The 'func' itself will return a new state.
            return func(processed_state, *args, **kwargs)
        return wrapper

    async def awrap_run(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def awrapper(state: ProdAgentState, *args, **kwargs) -> ProdAgentState:
            # Apply the rate_limit_func to the state before the main run
            processed_state = self._rate_limit_func(state)

            # If the rate limit logic decided to terminate early, return that state
            if processed_state.get("messages") and processed_state["messages"][-1].content == "Rate limited. Try again in 5min.":
                return processed_state

            # Otherwise, proceed with the original agent run function
            # The 'func' itself will return a new state.
            return await func(processed_state, *args, **kwargs)
        return awrapper

    def wrap_agent_call(self, func: Callable[..., Any]) -> Callable[..., Any]:
        # Agent call can be treated similar to a run for this middleware's purpose
        return self.wrap_run(func)

    async def awrap_agent_call(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.awrap_run(func)


# Original rate_limit_guard function (renamed and wrapped)
@traceable(name="custom_guard")
def _rate_limit_guard_func(state: ProdAgentState) -> ProdAgentState:
    """Custom middleware: rate limits + confidence tracking."""
    if state["error_count"] > 3:
        state["messages"].append(AIMessage("Rate limited. Try again in 5min."))
        return state

    # Track confidence (parsed from prior responses)
    if "confidence" in state["messages"][-1].additional_kwargs:
        state["confidence_scores"].append(state["messages"][-1].additional_kwargs["confidence"])

    return state

# Instantiate the custom middleware with the function
rate_limit_middleware_instance = CustomRateLimitMiddleware(_rate_limit_guard_func)

middleware = [email_pii_guard, summarizer, rate_limit_middleware_instance]
