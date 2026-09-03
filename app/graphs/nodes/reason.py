"""Node: Policy and Architecture Decision-Tree Reasoning LLM."""

import logging
from typing import Any, Dict, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.core.config import settings
from app.core.llm import get_llm
from app.graphs.nodes.base import BaseGraphNode
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class ReasonLLMNode(BaseGraphNode):
    """Generates authoritative system architecture, policy, and compliance recommendations."""

    name: str = "reason_llm"

    def __init__(self, model: Optional[Any] = None):
        self.model = model or get_llm(max_tokens=settings.PUBLISHER_MAX_TOKENS)

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name}")

        user_decisions = state.get("user_decisions_str") or "None"
        context_docs = state.get("context_docs_str") or "No reference documents."
        feedback = state.get("feedback") or ""
        chat_history = state.get("chat_history") or []

        system_prompt = (
            "You are an authoritative Enterprise Architecture, Policy & Standards Expert. "
            "Analyze the user's decision pathway, system specifications, and architecture context to provide "
            "a precise, step-by-step recommendation on the appropriate compliance pathway (Tier 1 Standard, Tier 2 Verification, Tier 3 Comprehensive Audit, or Custom Pathway).\n\n"
            f"Context Documents:\n{context_docs}\n\n"
            f"User Configured Pathway & Decisions:\n{user_decisions}\n"
        )

        user_query = feedback if feedback else "Please evaluate my current system architecture pathway and suggest next steps."

        messages = [
            SystemMessage(content=system_prompt),
            *chat_history,
            HumanMessage(content=user_query),
        ]

        # Process through Agent Middleware Pipeline (PII scrubbing, Summarization, Rate limiting)
        from app.middleware import default_agent_pipeline
        state, messages = await default_agent_pipeline.run_before_model(state, messages)

        # Tag the invocation with "PolicyExpert" for SSE/WebSocket token streaming
        config = {
            "tags": ["llm", "PolicyExpert"],
            "metadata": {"node": self.name},
        }

        try:
            response = await self.model.ainvoke(messages, config=config)
            state, response = await default_agent_pipeline.run_after_model(state, response)
            output_content = response.content if hasattr(response, "content") else str(response)

            return {
                "chat_history": [
                    HumanMessage(content=user_query),
                    AIMessage(content=output_content),
                ],
                "feedback": "",  # Clear feedback after processing
            }

        except Exception as e:
            logger.error(f"Reasoning LLM failed: {e}")
            error_reply = f"Reasoning analysis encountered an error: {str(e)}"
            return {
                "chat_history": [
                    HumanMessage(content=user_query),
                    AIMessage(content=error_reply),
                ],
            }


reason_llm_instance = ReasonLLMNode()


async def reason_llm(state: AgentState) -> Dict[str, Any]:
    return await reason_llm_instance(state)
