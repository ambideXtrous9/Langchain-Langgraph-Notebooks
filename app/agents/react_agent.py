"""Domain-Specific ReAct Agent with Tool Integration and Chat History Context."""

import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from app.core.config import settings
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


def get_default_tools() -> List[Any]:
    """Configures available search tools based on environment settings."""
    tools = []

    # 1. Tavily Search Tool (if API key available)
    if settings.TAVILY_API_KEY and settings.TAVILY_API_KEY != "mock-or-set-tavily-key":
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
            tools.append(TavilySearchResults(max_results=5, search_depth="basic"))
            logger.info("TavilySearchResults tool loaded.")
        except Exception as e:
            logger.warning(f"Could not load Tavily tool: {e}")

    # 2. DuckDuckGo Search Tool fallback
    if settings.ENABLE_DDG_SEARCH and not tools:
        try:
            from langchain_community.tools import DuckDuckGoSearchResults
            tools.append(DuckDuckGoSearchResults(max_results=5))
            logger.info("DuckDuckGoSearchResults tool loaded.")
        except Exception as e:
            logger.warning(f"Could not load DuckDuckGo tool: {e}")

    return tools


DEFAULT_EXPERT_PROMPT = (
    "You are an FDA and Medical Device Expert. Provide accurate, authoritative, "
    "and professional answers on medical devices. Do NOT produce any NSFW, "
    "explicit, or inappropriate content.\n"
    "Use the chat history to maintain context.\n\n"
    "For general questions beyond FDA or medical device topics, you should still answer, "
    "but also encourage the user to ask about FDA regulations or medical devices.\n\n"
    "If the question pertains directly to FDA or medical-device details (e.g. approvals, "
    "regulations, safety), you may use the web search_tool to fetch up‑to‑date information.\n\n"
    "Final Answer: Please respond concisely and factually."
)


def create_domain_react_agent(
    model: Optional[Any] = None,
    tools: Optional[List[Any]] = None,
    prompt: Optional[str] = None,
):
    """Creates a compiled ReAct agent graph with tools and prompt."""
    if model is None:
        model = get_llm(max_tokens=settings.GENERIC_CHAT_MAX_TOKENS)

    if tools is None:
        tools = get_default_tools()

    agent_prompt = prompt or DEFAULT_EXPERT_PROMPT

    return create_react_agent(
        model=model,
        tools=tools,
        prompt=agent_prompt,
    )


# Singleton instance for quick access
_default_agent = None


def get_default_react_agent():
    """Returns a singleton instance of the default ReAct agent."""
    global _default_agent
    if _default_agent is None:
        _default_agent = create_domain_react_agent()
    return _default_agent


async def execute_generic_chat(
    user_input: str,
    chat_history: Optional[List[BaseMessage]] = None,
    agent=None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Executes a chat turn maintaining conversational context from chat history."""
    if agent is None:
        agent = get_default_react_agent()

    try:
        from app.middleware import default_agent_pipeline

        # Run before_agent state validation (Rate limit, PII scrubbing)
        state_dict = {"user_input": user_input}
        if chat_history:
            state_dict["messages"] = list(chat_history)

        state_dict = await default_agent_pipeline.run_before_agent(state_dict)
        sanitized_input = state_dict.get("user_input", user_input)
        sanitized_history = state_dict.get("messages", chat_history or [])

        history_context = ""
        if sanitized_history:
            history_context = "\n".join([f"{msg.type}: {msg.content}" for msg in sanitized_history])

        formatted_content = f"Respond to this: {sanitized_input}"
        if history_context:
            formatted_content += f" with chat history for context:\n{history_context}"

        user_msg = {"role": "user", "content": formatted_content}

        llm_response = await agent.ainvoke({"messages": [user_msg]}, config=config)
        assistant_msg = llm_response["messages"][-1]

        raw_output = ""
        if isinstance(assistant_msg, AIMessage):
            raw_output = assistant_msg.content
        elif isinstance(assistant_msg, dict) and "content" in assistant_msg:
            raw_output = assistant_msg["content"]
        else:
            raw_output = str(assistant_msg)

        # Run after_model hook (sanitizing model output and tracking metrics)
        _, sanitized_output = await default_agent_pipeline.run_after_model(state_dict, raw_output)
        return str(sanitized_output)

    except Exception as e:
        logger.error(f"Reasoning LLM Error in genericChat: {e}")
        return f"LLM reasoning failed: {str(e)}"
