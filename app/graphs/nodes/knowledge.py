"""Node: Knowledge Base and Hybrid Retrieval."""

import logging
from typing import Any, Dict, Optional
from langchain_core.retrievers import BaseRetriever
from app.graphs.nodes.base import BaseGraphNode
from app.retrievers.ensemble import create_in_memory_retriever
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


class KnowledgeBaseNode(BaseGraphNode):
    """Retrieves relevant architecture guidance, compliance standards, and benchmarks to build decision tree context."""

    name: str = "knowledge_base"

    def __init__(self, retriever: Optional[BaseRetriever] = None):
        self.retriever = retriever or create_in_memory_retriever()

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"Executing Node: {self.name}")

        query_terms = []
        if state.get("user_decisions_str"):
            query_terms.append(state["user_decisions_str"])
        if state.get("feedback"):
            query_terms.append(state["feedback"])

        search_query = " ".join(query_terms) if query_terms else "Enterprise system architecture compliance standard pathway"

        try:
            docs = await self.retriever.ainvoke(search_query)
            retrieved_text = "\n\n".join([f"[{doc.metadata.get('source', 'doc')}]: {doc.page_content}" for doc in docs])
        except Exception as e:
            logger.warning(f"Retrieval in knowledge base failed: {e}. Using fallback reference context.")
            retrieved_text = (
                "[ISO 27001]: Information Security Management System Controls.\n"
                "[NIST 800-53]: Security and Privacy Controls for Information Systems and Organizations."
            )

        existing_context = state.get("context_docs_str") or ""
        combined_context = f"{existing_context}\n\n[Retrieved Policy & Standards Knowledge]:\n{retrieved_text}".strip()

        return {
            "context_docs_str": combined_context,
        }


knowledge_base_instance = KnowledgeBaseNode()


async def build_decision_tree_prompt(state: AgentState) -> Dict[str, Any]:
    return await knowledge_base_instance(state)
