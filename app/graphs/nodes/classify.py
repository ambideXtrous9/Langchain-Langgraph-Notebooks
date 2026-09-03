"""Node: Classify Topic and Route."""

import logging
from typing import Any, Dict
from app.graphs.nodes.base import BaseGraphNode
from app.agents.classifier_agent import ClassifierAgent
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class ClassifyNode(BaseGraphNode):
    """Classifies user input or current topic into 'generic', 'policy', or 'exit'."""

    name: str = "classify_node"

    def __init__(self, classifier: ClassifierAgent = None):
        self.classifier = classifier or ClassifierAgent()

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name}")

        # Evaluate the most recent feedback, user_decisions, or fallback to choices
        topic = state.get("feedback") or state.get("user_decisions_str") or "Initial inquiry"
        if isinstance(topic, dict):
            topic = str(topic)

        chat_history = state.get("chat_history") or []
        classification_result = await self.classifier.aclassify(
            str(topic),
            chat_history=chat_history,
        )
        logger.info(f"Classification Result: {classification_result}")

        return {
            "classification": classification_result,
        }


classify_node_instance = ClassifyNode()


async def classify_node(state: AgentState) -> Dict[str, Any]:
    return await classify_node_instance(state)
