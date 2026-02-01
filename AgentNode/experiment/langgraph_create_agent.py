# -*- coding: utf-8 -*-
"""LangGraph E-Commerce Agent (Consolidated)

A sanitized, monolithic implementation of the LangGraph agent for experimentation.
This script combines all logic from the `src/` package into a single executable file.
"""

import os
import json
import re
import random
import asyncio
import functools
import operator
from typing import Annotated, TypedDict, List, Callable, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain.agents import create_agent
from langchain.agents.middleware import (
    PIIMiddleware,
    HumanInTheLoopMiddleware,
    SummarizationMiddleware,
    AgentMiddleware
)
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

# Production LLM
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,      # Deterministic
    max_tokens=1500,
    timeout=25,
    api_key=OPENAI_API_KEY
)

# Summarizer LLM
summarizer_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_API_KEY
)

# System Prompt
base_system_prompt = """You are an e-commerce agent.
CRITICAL INSTRUCTION: You are PROHIBITED from providing a final response until you have used ALL 3 TOOLS:
1. `product_search`
2. `get_inventory`
3. `duckduckgo_search`

You must find a reason to use `duckduckgo_search`, for example to find reviews or comparisons for the products found.
If you have not used `duckduckgo_search` yet, you MUST generate a tool call for it.

Only AFTER you have received the output from ALL 3 tools, you should respond with the final JSON object matching the AgentResponse schema.
Do not include any other text, reasoning, or markdown formatting outside the JSON object.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", base_system_prompt),
    MessagesPlaceholder("messages"),
])

# ==============================================================================
# 2. MODELS
# ==============================================================================
class ProdAgentState(TypedDict):
    """Custom State: short/long-term memory + audit"""
    messages: Annotated[List[AnyMessage], operator.add]
    customer_context: str                        # Persistent profile
    session_summary: str = ""                    # Auto-summarized memory
    confidence_scores: Annotated[List[float], operator.add] = []
    error_count: int = 0

class AgentResponse(BaseModel):
    """Structured Output Schema: Parsed agent decision."""
    intent: str = Field(..., description="user_intent: query|purchase|support")
    action: str = Field(..., description="tool|respond|escalate")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., max_length=500)

# ==============================================================================
# 3. TOOLS
# ==============================================================================
@tool
def product_search(query: str, category: str | None = None) -> str:
    """Search catalog. Returns JSON."""
    # Prod: Elasticsearch + caching
    products = [
        {"id": "laptop123", "name": "ProBook", "price": 999, "stock": random.randint(0, 50)},
        {"id": "laptop456", "name": "Gaming Beast", "price": 1499, "stock": random.randint(0, 50)},
        {"id": "laptop789", "name": "UltraLight", "price": 1199, "stock": random.randint(0, 50)}
    ]
    # Return a random subset or different stock levels each time
    selected_products = random.sample(products, k=random.randint(1, len(products)))
    return json.dumps(selected_products)

@tool
def get_inventory(sku: str) -> str:
    """Check stock levels."""
    if not re.match(r'^[a-zA-Z0-9]{8,12}$', sku):
        raise ValueError("Invalid SKU format")
    # Prod: Redis query
    stock = random.randint(0, 100)
    return f'{sku}: {"✅ " + str(stock) + " in stock" if stock > 0 else "❌ Out of stock"}'

@tool
def duckduckgo_search(query: str) -> str:
    """Search DuckDuckGo for information based on the query."""
    search = DuckDuckGoSearchAPIWrapper()
    return search.run(query)

tools = [product_search, get_inventory, duckduckgo_search]

# ==============================================================================
# 4. MIDDLEWARE
# ==============================================================================
# Define the custom middleware class to wrap the rate_limit_guard function
class CustomRateLimitMiddleware(AgentMiddleware):
    def __init__(self, rate_limit_func: Callable[[ProdAgentState], ProdAgentState]):
        self._rate_limit_func = rate_limit_func

    def wrap_tool_call(self, tool_request: Any, execute_tool: Callable[..., Any], extra_arg: Any = None) -> Any:
        if extra_arg is not None:
            return execute_tool(tool_request, extra_arg)
        return execute_tool(tool_request)

    async def awrap_tool_call(self, tool_request: Any, execute_tool: Callable[..., Any], extra_arg: Any = None) -> Any:
        if extra_arg is not None:
            return await execute_tool(tool_request, extra_arg)
        return await execute_tool(tool_request)

    def wrap_run(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(state: ProdAgentState, *args, **kwargs) -> ProdAgentState:
            processed_state = self._rate_limit_func(state)
            if processed_state.get("messages") and processed_state["messages"][-1].content == "Rate limited. Try again in 5min.":
                return processed_state
            return func(processed_state, *args, **kwargs)
        return wrapper

    async def awrap_run(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def awrapper(state: ProdAgentState, *args, **kwargs) -> ProdAgentState:
            processed_state = self._rate_limit_func(state)
            if processed_state.get("messages") and processed_state["messages"][-1].content == "Rate limited. Try again in 5min.":
                return processed_state
            return await func(processed_state, *args, **kwargs)
        return awrapper

    def wrap_agent_call(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.wrap_run(func)

    async def awrap_agent_call(self, func: Callable[..., Any]) -> Callable[..., Any]:
        return self.awrap_run(func)

@traceable(name="custom_guard")
def _rate_limit_guard_func(state: ProdAgentState) -> ProdAgentState:
    """Custom middleware: rate limits + confidence tracking."""
    if state["error_count"] > 3:
        state["messages"].append(AIMessage("Rate limited. Try again in 5min."))
        return state
    # Track confidence (parsed from prior responses)
    if state["messages"] and hasattr(state["messages"][-1], "additional_kwargs") and "confidence" in state["messages"][-1].additional_kwargs:
        state["confidence_scores"].append(state["messages"][-1].additional_kwargs["confidence"])
    return state

email_pii_guard = PIIMiddleware(
    pii_type="email",
    strategy="redact",
    apply_to_input=True,
    apply_to_output=True
)

hil_guard = HumanInTheLoopMiddleware(
    interrupt_on={"get_inventory": True}
)

summarizer = SummarizationMiddleware(
    model=summarizer_llm,
    trigger=("tokens", 4000),
    summary_key="session_summary"
)

rate_limit_middleware_instance = CustomRateLimitMiddleware(_rate_limit_guard_func)

middleware = [email_pii_guard, summarizer, rate_limit_middleware_instance]

# ==============================================================================
# 5. AGENT Setup
# ==============================================================================
agent = create_agent(
    llm,
    tools,
    state_schema=ProdAgentState,
    response_format=AgentResponse,
    system_prompt=base_system_prompt,
    middleware=[],  # Temporarily disable all middleware for debugging/simplicity
    checkpointer=MemorySaver(),
)

# ==============================================================================
# 6. MAIN EXECUTION
# ==============================================================================
@traceable
async def handle_customer_query(customer_id: str, query: str, context: str):
    config = {"configurable": {"thread_id": f"customer_{customer_id}"}}

    input_state = {
        "messages": [HumanMessage(content=query)],
        "customer_context": context,
    }

    final_message = None
    # Streaming for real-time UX
    print(f"\n🚀 Starting Query for {customer_id}...")
    async for event in agent.astream(input_state, config, stream_mode="values"):
        current_messages = event["messages"]
        
        # Display latest activity
        if current_messages:
            last_msg = current_messages[-1]
            print(f"\n[{type(last_msg).__name__}]: {last_msg.content}")
            
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                print(f"  🛠️ Tool calls: {last_msg.tool_calls}")
            
            if hasattr(last_msg, 'structured_response') and last_msg.structured_response:
                 print(f"  📊 Structured Response: {last_msg.structured_response}")

            final_message = last_msg

    if final_message:
        return final_message
    else:
        raise ValueError("No response received from the agent.")

if __name__ == "__main__":
    asyncio.run(handle_customer_query(
        customer_id="user_456",
        query="Are there any affordable gaming laptops under $1500 currently in stock?",
        context="VIP customer, prefers gaming laptops"
    ))
