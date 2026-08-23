"""Summarization Middleware for Compressing Message History and Context Management."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from app.middleware.base import AgentMiddleware

logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """Fast, accurate token estimation (~4 characters per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[BaseMessage]) -> int:
    """Calculates total estimated tokens across a list of BaseMessages."""
    total = 0
    for msg in messages:
        if isinstance(msg.content, str):
            total += estimate_token_count(msg.content)
    return total


class SummarizationMiddleware(AgentMiddleware):
    """Monitors token count and message length, summarizing older messages when thresholds are reached."""

    name: str = "summarization"

    def __init__(
        self,
        trigger: Optional[List[Tuple[str, int]]] = None,
        preserve_recent_count: int = 4,
        llm: Optional[Any] = None,
    ):
        """
        Initializes SummarizationMiddleware.

        Args:
            trigger: List of trigger conditions, e.g. [("tokens", 1000), ("messages", 8)].
            preserve_recent_count: Number of most recent messages to keep uncompressed.
            llm: Optional LLM instance to generate high-fidelity semantic summaries.
        """
        self.trigger = trigger or [("tokens", 1200), ("messages", 8)]
        self.preserve_recent = preserve_recent_count
        self.llm = llm

    def _should_summarize(self, messages: List[BaseMessage]) -> bool:
        """Evaluates whether any configured trigger threshold has been crossed."""
        if len(messages) <= self.preserve_recent:
            return False

        for metric, threshold in self.trigger:
            if metric == "messages" and len(messages) >= threshold:
                return True
            elif metric == "tokens" and estimate_messages_tokens(messages) >= threshold:
                return True
        return False

    async def _generate_summary(self, older_messages: List[BaseMessage]) -> str:
        """Generates a compressed summary of older messages."""
        if self.llm:
            try:
                transcript = "\n".join([f"{msg.type.upper()}: {msg.content}" for msg in older_messages if isinstance(msg.content, str)])
                prompt = (
                    "Summarize the following prior dialogue into a concise bulleted historical context summary, "
                    "retaining key regulatory classifications, device details, and previous user requests:\n\n"
                    f"{transcript}"
                )
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                return str(response.content).strip()
            except Exception as e:
                logger.warning(f"LLM Summarization failed ({e}), falling back to heuristic summary.")

        # Heuristic Summarizer Fallback
        summary_snippets = []
        for msg in older_messages:
            if isinstance(msg.content, str) and msg.content.strip():
                snippet = msg.content.strip().split("\n")[0][:120]
                summary_snippets.append(f"- {msg.type.capitalize()}: {snippet}")
        return "Key points discussed:\n" + "\n".join(summary_snippets)

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        """Compresses older messages if trigger criteria are met."""
        if not messages or not self._should_summarize(messages):
            return state, messages

        logger.info(f"Summarization triggered for {len(messages)} messages (threshold met).")

        # Separate system messages, older history, and recent messages
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        conversation = [m for m in messages if not isinstance(m, SystemMessage)]

        if len(conversation) <= self.preserve_recent:
            return state, messages

        older_messages = conversation[:-self.preserve_recent]
        recent_messages = conversation[-self.preserve_recent:]

        summary_text = await self._generate_summary(older_messages)
        summary_message = SystemMessage(
            content=f"[Context Summary of {len(older_messages)} Prior Messages]:\n{summary_text}"
        )

        compressed_messages = system_messages + [summary_message] + recent_messages
        logger.info(f"Compressed message list from {len(messages)} to {len(compressed_messages)} messages.")

        state["messages_summarized"] = True
        return state, compressed_messages
