"""Structured JSON Classification Agent with Pydantic Validation and Retry Loop."""

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from app.core.config import settings
from app.core.llm import get_llm
from app.schemas.state import Classify

logger = logging.getLogger(__name__)


class ClassifierAgent:
    """Agent that classifies input topics into 'generic', 'policy', or 'exit' with strict Pydantic JSON validation."""

    def __init__(self, model: Optional[Any] = None, max_retries: int = 3):
        self.model = model or get_llm(temperature=0.0, max_tokens=300)
        self.parser = PydanticOutputParser(pydantic_object=Classify)
        self.max_retries = max_retries
        self.format_instructions = self.parser.get_format_instructions()

    def _build_prompt(self, user_content: str, chat_context: str = "") -> str:
        context_section = f"\nRecent Conversation Context:\n{chat_context}\n" if chat_context else ""
        return (
            "You are an expert system architecture, policy, and compliance standards decision-tree assistant.\n\n"
            "Your output MUST conform exactly to this JSON schema (no extra markdown outside the JSON):\n"
            f"{self.format_instructions}\n\n"
            f"{context_section}"
            "Add a key `classification` with value either 'generic', 'policy', or 'exit':\n"
            "- If the query is an ongoing discussion or question about architecture standards, policies, system tiers, specifications, "
            "compliance pathways, or follow-ups to the conversation context (e.g. 'why', 'elaborate', 'tell me more', 'what about verification'), set `classification` to 'policy'.\n"
            "- If the query is a pure greeting or completely unrelated chit-chat with no policy/standards context, set `classification` to 'generic'.\n"
            "- If the query is to exit, stop, or end the conversation (e.g. 'exit', 'quit', 'bye'), set `classification` to 'exit'.\n\n"
            "Also add a key `reply`:\n"
            "- If `classification` is 'generic', `reply` must be a friendly, helpful natural language response encouraging policy and architecture topics.\n"
            "- If `classification` is 'policy', `reply` must be the exact string 'POLICY'.\n"
            "- If `classification` is 'exit', `reply` must be the exact string 'exit'.\n\n"
            f"User input to classify:\n{user_content}"
        )

    async def aclassify(
        self,
        topic: str,
        chat_history: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously classifies the topic with self-correction retry loop."""
        chat_context = ""
        if chat_history:
            recent_msgs = chat_history[-4:]  # Last 2 turns
            chat_context = "\n".join(
                f"{getattr(m, 'type', 'msg')}: {getattr(m, 'content', str(m))[:120]}"
                for m in recent_msgs
            )

        attempt = 0
        current_content = f"Classify this topic: {topic}"

        while attempt < self.max_retries:
            attempt += 1
            prompt_text = self._build_prompt(current_content, chat_context=chat_context)

            # Modern structured output path
            if hasattr(self.model, "with_structured_output"):
                try:
                    structured_llm = self.model.with_structured_output(Classify)
                    result = await structured_llm.ainvoke(prompt_text)
                    if isinstance(result, Classify):
                        return result.model_dump()
                    elif isinstance(result, dict) and "classification" in result:
                        return result
                except Exception as structured_err:
                    logger.debug(f"Structured output call skipped/failed: {structured_err}")

            try:
                response = await self.model.ainvoke(prompt_text)
                raw_text = response.content if hasattr(response, "content") else str(response)

                # Clean markdown backticks if wrapped
                cleaned_text = raw_text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()

                parsed: Classify = self.parser.parse(cleaned_text)
                return parsed.model_dump()

            except (ValidationError, Exception) as e:
                logger.warning(f"[Attempt {attempt}/{self.max_retries}] Classification parsing failed: {e}")
                current_content += "\n\nNote: Your previous output did not match the required JSON schema. Please return pure JSON only."

        # Fallback if LLM repeatedly fails or mock key is used
        logger.warning(f"All {self.max_retries} attempts failed. Applying rule-based heuristic classification.")
        topic_lower = topic.lower().strip()
        if any(w in topic_lower for w in ["exit", "quit", "stop", "bye"]):
            return {"classification": "exit", "reply": "exit"}
        elif chat_history and len(chat_history) > 0:
            # If in an active conversation, default follow-up to policy reasoning
            return {"classification": "policy", "reply": "POLICY"}
        elif any(w in topic_lower for w in ["policy", "tier", "standard", "system", "spec", "path", "node", "benchmark", "compliance", "audit", "architecture"]):
            return {"classification": "policy", "reply": "POLICY"}
        else:
            return {"classification": "generic", "reply": "I can help you with system architecture and policy standards. How can I assist you?"}


# Helper function
async def classify_topic(topic: str, chat_history: Optional[List[Any]] = None) -> Dict[str, Any]:
    """Helper to classify a topic with the default classifier."""
    classifier = ClassifierAgent()
    return await classifier.aclassify(topic, chat_history=chat_history)
