"""Personally Identifiable Information (PII) Guard Middleware."""

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from app.middleware.base import AgentMiddleware

# Regex Patterns for Sensitive Identifiers
PII_PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "medical_id": re.compile(r"\b(?:MRN|PATIENT_ID|PATIENT|MED_ID)[:\s#]*[A-Z0-9-]{4,12}\b", re.IGNORECASE),
    "ipv4": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
}


class PIIMiddleware(AgentMiddleware):
    """Detects and sanitizes PII from user inputs, agent states, and LLM completions."""

    name: str = "pii_guard"

    def __init__(
        self,
        strategy: str = "mask",
        pii_types: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, str]] = None,
    ):
        """
        Initializes PIIMiddleware.

        Args:
            strategy: Replacement strategy ('mask', 'redact', 'hash').
            pii_types: List of PII types to guard (default: all).
            custom_patterns: Additional regex patterns {name: regex_str}.
        """
        self.strategy = strategy.lower()
        if self.strategy not in {"mask", "redact", "hash"}:
            raise ValueError(f"Unsupported PII strategy '{strategy}'. Use 'mask', 'redact', or 'hash'.")

        self.patterns = dict(PII_PATTERNS)
        if custom_patterns:
            for name, pattern_str in custom_patterns.items():
                self.patterns[name] = re.compile(pattern_str, re.IGNORECASE)

        if pii_types:
            self.active_patterns = {k: v for k, v in self.patterns.items() if k in pii_types}
        else:
            self.active_patterns = self.patterns

    def _replace_match(self, match: re.Match, pii_type: str) -> str:
        """Computes replacement token based on active strategy."""
        val = match.group(0)
        if self.strategy == "mask":
            return f"[{pii_type.upper()}_REDACTED]"
        elif self.strategy == "redact":
            return "***"
        elif self.strategy == "hash":
            hash_prefix = hashlib.sha256(val.encode("utf-8")).hexdigest()[:8]
            return f"[{pii_type.upper()}_HASH:{hash_prefix}]"
        return "[REDACTED]"

    def sanitize_text(self, text: str) -> str:
        """Sanitizes text against all active PII patterns."""
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pii_type, pattern in self.active_patterns.items():
            sanitized = pattern.sub(lambda m, pt=pii_type: self._replace_match(m, pt), sanitized)
        return sanitized

    def sanitize_data(self, data: Any) -> Any:
        """Recursively sanitizes dicts, lists, and strings."""
        if isinstance(data, str):
            return self.sanitize_text(data)
        elif isinstance(data, dict):
            return {k: self.sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_data(item) for item in data]
        return data

    def sanitize_message(self, message: BaseMessage) -> BaseMessage:
        """Sanitizes the content of a LangChain BaseMessage."""
        if isinstance(message.content, str):
            sanitized_content = self.sanitize_text(message.content)
            # Create a copy with sanitized content
            if isinstance(message, HumanMessage):
                return HumanMessage(content=sanitized_content, additional_kwargs=message.additional_kwargs)
            elif isinstance(message, AIMessage):
                return AIMessage(content=sanitized_content, additional_kwargs=message.additional_kwargs)
            elif isinstance(message, SystemMessage):
                return SystemMessage(content=sanitized_content, additional_kwargs=message.additional_kwargs)
            elif isinstance(message, ToolMessage):
                return ToolMessage(
                    content=sanitized_content,
                    tool_call_id=message.tool_call_id,
                    additional_kwargs=message.additional_kwargs,
                )
            else:
                return type(message)(content=sanitized_content, additional_kwargs=message.additional_kwargs)
        return message

    async def before_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizes input strings and messages in state before agent execution."""
        sanitized_state = dict(state)
        for key in ["user_input", "topic", "query", "device_specs"]:
            if key in sanitized_state and isinstance(sanitized_state[key], str):
                sanitized_state[key] = self.sanitize_text(sanitized_state[key])

        if "messages" in sanitized_state and isinstance(sanitized_state["messages"], list):
            sanitized_state["messages"] = [
                self.sanitize_message(m) if isinstance(m, BaseMessage) else self.sanitize_data(m)
                for m in sanitized_state["messages"]
            ]
        return sanitized_state

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[BaseMessage],
    ) -> Tuple[Dict[str, Any], List[BaseMessage]]:
        """Sanitizes all messages immediately before LLM call."""
        sanitized_messages = [
            self.sanitize_message(m) if isinstance(m, BaseMessage) else m
            for m in messages
        ]
        return state, sanitized_messages

    async def after_model(
        self,
        state: Dict[str, Any],
        response: Any,
    ) -> Tuple[Dict[str, Any], Any]:
        """Sanitizes model output to prevent any PII echo."""
        if isinstance(response, BaseMessage) and isinstance(response.content, str):
            response = self.sanitize_message(response)
        elif isinstance(response, str):
            response = self.sanitize_text(response)
        elif isinstance(response, dict):
            response = self.sanitize_data(response)
        return state, response
