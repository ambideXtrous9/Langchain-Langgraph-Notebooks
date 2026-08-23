"""Base Class for LangGraph Nodes."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class BaseGraphNode(ABC):
    """Abstract Base Class for LangGraph node implementations."""

    name: str = "base_node"

    @abstractmethod
    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Executes the node logic asynchronously and returns state updates."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
