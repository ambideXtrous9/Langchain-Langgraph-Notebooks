"""Node: Human-in-the-Loop Process Feedback with LangGraph Interrupt."""

import logging
from typing import Any, Dict
from langgraph.types import interrupt
from app.graphs.nodes.base import BaseGraphNode
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class ProcessFeedbackNode(BaseGraphNode):
    """Halts graph execution using LangGraph `interrupt` to collect user feedback or exit command."""

    name: str = "process_feedback"

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name} (Interrupting execution for user input)")

        # LangGraph interrupt suspends graph execution until a resume command is sent
        raw_feedback = interrupt("Please provide detailed feedback or type 'exit' to end:")
        feedback_str = str(raw_feedback).strip() if raw_feedback is not None else ""

        logger.info(f"Received resumed user feedback: '{feedback_str}'")

        return {
            "feedback": feedback_str,
        }


process_feedback_instance = ProcessFeedbackNode()


async def process_feedback(state: AgentState) -> Dict[str, Any]:
    return await process_feedback_instance(state)
