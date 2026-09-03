"""Node: Device Summary and Metadata Processing."""

import logging
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.llm import get_llm
from app.graphs.nodes.base import BaseGraphNode
from app.schemas.state import AgentState, get_device_data

logger = logging.getLogger(__name__)


class DeviceSummaryNode(BaseGraphNode):
    """Processes, extracts, and summarizes user-provided system architecture metadata."""

    name: str = "device_summary"

    def __init__(self, model: Optional[Any] = None):
        self.model = model or get_llm(temperature=0.0, max_tokens=600)

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name}")

        device_data = get_device_data(state)
        if not device_data.strip():
            return {
                "context_docs_str": "No system specifications provided.",
            }

        try:
            prompt = (
                "You are an enterprise system and technical architecture analyst. Analyze and summarize the following "
                "system data into key architecture parameters (Intended Use, Core Technology, System Tier, Baseline References):\n\n"
                f"{device_data}"
            )
            response = await self.model.ainvoke(prompt)
            summary_content = response.content if hasattr(response, "content") else str(response)

            existing_context = state.get("context_docs_str") or ""
            updated_context = f"{existing_context}\n\n[System Specification Summary]:\n{summary_content}".strip()

            return {"context_docs_str": updated_context}

        except Exception as e:
            logger.warning(f"System summary generation failed: {e}. Passing raw specification data.")
            return {"context_docs_str": f"[Raw System Data]: {device_data}"}


device_summary_instance = DeviceSummaryNode()


async def device_summary(state: AgentState) -> Dict[str, Any]:
    return await device_summary_instance(state)
