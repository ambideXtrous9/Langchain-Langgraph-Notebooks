"""Node: Extract User Decision and Initial Pathway."""

import json
import logging
from typing import Any, Dict
from app.graphs.nodes.base import BaseGraphNode
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class UserInitPathNode(BaseGraphNode):
    """Parses initial user choices, formats decisions, and sets up path context."""

    name: str = "user_initpath"

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name}")

        user_choices = state.get("user_choices") or {}
        feedback = state.get("feedback") or ""

        # Format user decisions into human-readable string
        if isinstance(user_choices, dict):
            decisions_str = "\n".join([f"- {k}: {v}" for k, v in user_choices.items()])
        else:
            decisions_str = str(user_choices)

        current_path_str = f"Initial Path Configured: {json.dumps(user_choices)}"

        logger.debug(f"Formatted decisions: {decisions_str}")
        return {
            "current_path_str": current_path_str,
            "user_decisions_str": decisions_str,
        }


# Function wrapper for functional graph node registration
user_initpath_node = UserInitPathNode()


async def extract_user_decision_and_path(state: AgentState) -> Dict[str, Any]:
    return await user_initpath_node(state)
