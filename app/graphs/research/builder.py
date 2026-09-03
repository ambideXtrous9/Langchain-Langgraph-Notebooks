"""StateGraph Builder for the Parallel Research, Critic, and Publisher Architecture."""

import logging
import os
from typing import Optional
from langgraph.graph import END, START, StateGraph
from app.schemas.research import ResearchState
from app.graphs.research.nodes import (
    planner_node,
    approver_agent_node,
    researcher_dispatcher_node,
    researcher_node,
    synthesizer_node,
    fact_critic_node,
    style_critic_1_node,
    style_critic_2_node,
    publisher_node,
)

logger = logging.getLogger(__name__)


def route_approver_decision(state: ResearchState) -> str:
    """Routes based on whether the Approver Agent approved the plan or requested revision."""
    is_approved = state.get("plan_approved", False)
    if is_approved:
        logger.info("[Routing] Plan approved -> Routing to researcher_dispatcher")
        return "dispatch"
    else:
        logger.info("[Routing] Plan needs revision -> Routing back to planner")
        return "revise"


class ResearchGraphBuilder:
    """Builds and compiles the Parallel Research StateGraph."""

    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer
        self.workflow: Optional[StateGraph] = None
        self.compiled_graph = None

    def build(self):
        """Constructs the workflow graph matching the exact parallel architecture."""
        workflow = StateGraph(state_schema=ResearchState)

        # 1. Register Graph Nodes (with defer=True on publisher)
        workflow.add_node("planner", planner_node)
        workflow.add_node("approver", approver_agent_node)
        workflow.add_node("researcher_dispatcher", researcher_dispatcher_node)
        workflow.add_node("researcher", researcher_node)
        workflow.add_node("synthesizer", synthesizer_node)
        workflow.add_node("fact_critic", fact_critic_node)
        workflow.add_node("style_critic_1", style_critic_1_node)
        workflow.add_node("style_critic_2", style_critic_2_node)
        workflow.add_node("publisher", publisher_node, defer=True)

        # 2. Add Edges
        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "approver")

        # 3. Conditional feedback loop: approver -> planner or researcher_dispatcher
        workflow.add_conditional_edges(
            "approver",
            route_approver_decision,
            {
                "dispatch": "researcher_dispatcher",
                "revise": "planner",
            },
        )

        # 4. Research pipeline
        workflow.add_edge("researcher_dispatcher", "researcher")
        workflow.add_edge("researcher", "synthesizer")

        # 5. Parallel Fan-Out from Synthesizer
        workflow.add_edge("synthesizer", "fact_critic")
        workflow.add_edge("synthesizer", "style_critic_1")
        workflow.add_edge("style_critic_1", "style_critic_2")

        # 6. Fan-In to Publisher (defer=True waits for both parallel branches)
        workflow.add_edge("fact_critic", "publisher")
        workflow.add_edge("style_critic_2", "publisher")
        workflow.add_edge("publisher", END)

        self.workflow = workflow
        return self

    def compile(self, checkpointer=None):
        """Compiles the StateGraph with the provided checkpointer."""
        if self.workflow is None:
            self.build()

        active_checkpointer = checkpointer or self.checkpointer
        self.compiled_graph = self.workflow.compile(checkpointer=active_checkpointer)
        logger.info("Research StateGraph compiled successfully.")
        return self.compiled_graph

    def save_visualization(self, output_path: str = "app/static/research_graph.png") -> None:
        """Saves a visual PNG and Mermaid text definition of the research graph."""
        from app.graphs.visualizer import export_graph_visualization

        export_graph_visualization(self.compiled_graph, output_path)


def create_research_graph(checkpointer=None):
    """Factory helper creating and compiling the production research graph."""
    builder = ResearchGraphBuilder(checkpointer=checkpointer)
    builder.build()
    return builder.compile()
