"""Conditional Edge Routing Logic for StateGraph."""

import logging
from typing import Literal
from app.schemas.state import AgentState, get_device_data

logger = logging.getLogger(__name__)


def decide_start_node(state: AgentState) -> Literal["end", "feedbackloop", "device", "knowledge"]:
    """Determines the next node from 'classify_node' based on user intent and input configuration.

    Routing rules:
    - 'exit' classification -> routes to 'end' (END)
    - 'generic' classification -> routes to 'feedbackloop' (process_feedback)
    - 'useDeviceData' is True and device data provided -> routes to 'device' (device_summary)
    - 'useDeviceData' is False or empty device data -> routes to 'knowledge' (knowledge_base)
    """
    classification = state.get("classification") or {}
    class_type = classification.get("classification") if isinstance(classification, dict) else ""

    logger.info(f"Routing Decision: classification='{class_type}', useDeviceData={state.get('useDeviceData')}")

    chat_history = state.get("chat_history") or []
    has_history = len(chat_history) > 0
    device_data = get_device_data(state)

    if class_type == "exit":
        return "end"
    elif state.get("useDeviceData") is True and device_data:
        return "device"
    elif class_type == "generic" and not has_history:
        # Only brand-new uncontextualized generic greetings route directly to feedback loop
        return "feedbackloop"
    else:
        # All ongoing thread conversations & policy/standards queries route to knowledge base and reason LLM
        return "knowledge"
