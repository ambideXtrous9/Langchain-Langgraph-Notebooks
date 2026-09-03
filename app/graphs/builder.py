"""LangGraph StateGraph Builder and Compiler."""

import logging
import os
from typing import Optional
from langgraph.graph import END, START, StateGraph
from app.schemas.state import AgentState
from app.graphs.nodes import (
    extract_user_decision_and_path,
    classify_node,
    device_summary,
    build_decision_tree_prompt,
    reason_llm,
    process_feedback,
)
from app.graphs.routing import decide_start_node

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builder class responsible for wiring nodes, conditional branches, and compiling the StateGraph."""

    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer
        self.workflow: Optional[StateGraph] = None
        self.compiled_graph = None

    def build(self):
        """Constructs the workflow and connects all graph nodes and edges."""
        workflow = StateGraph(state_schema=AgentState)

        # 1. Register Graph Nodes
        workflow.add_node("user_initpath", extract_user_decision_and_path)
        workflow.add_node("classify_node", classify_node)
        workflow.add_node("device_summary", device_summary)
        workflow.add_node("knowledge_base", build_decision_tree_prompt)
        workflow.add_node("reason_llm", reason_llm)
        workflow.add_node("process_feedback", process_feedback)

        # 2. Configure Entry Point using standard START edge
        workflow.add_edge(START, "user_initpath")

        # 3. Add Edges & Conditional Routing
        workflow.add_edge("user_initpath", "classify_node")

        workflow.add_conditional_edges(
            "classify_node",
            decide_start_node,
            {
                "feedbackloop": "process_feedback",
                "device": "device_summary",
                "knowledge": "knowledge_base",
                "end": END,
            },
        )

        workflow.add_edge("device_summary", "knowledge_base")
        workflow.add_edge("knowledge_base", "reason_llm")
        workflow.add_edge("reason_llm", "process_feedback")
        workflow.add_edge("process_feedback", "classify_node")

        self.workflow = workflow
        return self

    def compile(self, checkpointer=None):
        """Compiles the StateGraph with the provided checkpointer."""
        if self.workflow is None:
            self.build()

        active_checkpointer = checkpointer or self.checkpointer
        self.compiled_graph = self.workflow.compile(checkpointer=active_checkpointer)
        logger.info("LangGraph StateGraph compiled successfully.")
        return self.compiled_graph

    def save_visualization(self, output_path: str = "app/static/graph.png") -> None:
        """Saves a visual PNG and Mermaid text representation of the graph to disk."""
        from app.graphs.visualizer import export_graph_visualization

        export_graph_visualization(self.compiled_graph, output_path)


def create_graph(checkpointer=None):
    """Factory helper creating and compiling the production graph."""
    builder = GraphBuilder(checkpointer=checkpointer)
    builder.build()
    return builder.compile()
