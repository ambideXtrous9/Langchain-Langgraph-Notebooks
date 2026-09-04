"""StateGraph Builder for the Institutional NSE Stock Analysis Architecture."""

import logging
from typing import Optional
from langgraph.graph import END, START, StateGraph
from app.schemas.stock_analysis import StockAnalysisState
from app.graphs.stock_analysis.nodes import (
    deterministic_ingest_node,
    richness_assessor_node,
    planner_node,
    analyst_fanout_node,
    reflection_node,
    followup_analysis_node,
    gather_node,
    verify_node,
    judge_node,
    narrative_enrich_node,
    chart_agent_node,
    section_writers_node,
    exec_summary_node,
    assembler_node,
    chart_curator_node,
)

logger = logging.getLogger(__name__)


def route_reflection(state: StockAnalysisState) -> str:
    """Routes based on reflection evaluation: gap funded -> followup, else -> gather."""
    if state.get("reflection_gap_funded", False):
        logger.info("[Routing] Reflection funded gap -> Routing to followup_analysis")
        return "followup"
    logger.info("[Routing] No critical gaps -> Routing directly to gather")
    return "gather"


def route_gather(state: StockAnalysisState) -> str:
    """Routes based on whether proposed findings exist: findings exist -> verify, else -> judge (judge_gate)."""
    findings = state.get("proposed_findings", [])
    if findings:
        logger.info(f"[Routing] {len(findings)} proposed findings -> Routing to verify")
        return "verify"
    logger.info("[Routing] No findings proposed -> Bypassing verify to judge")
    return "judge"


class StockAnalysisGraphBuilder:
    """Builds and compiles the Multi-Agent NSE Stock Analysis StateGraph."""

    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer
        self.workflow: Optional[StateGraph] = None
        self.compiled_graph = None

    def build(self):
        """Constructs the workflow matching the multi-agent architecture diagram."""
        workflow = StateGraph(state_schema=StockAnalysisState)

        # 1. Register Graph Nodes
        workflow.add_node("deterministic_ingest", deterministic_ingest_node)
        workflow.add_node("richness_assessor", richness_assessor_node)
        workflow.add_node("planner", planner_node)
        workflow.add_node("analyst_fanout", analyst_fanout_node)
        workflow.add_node("reflection", reflection_node)
        workflow.add_node("followup_analysis", followup_analysis_node)
        workflow.add_node("gather", gather_node)
        workflow.add_node("verify", verify_node)
        workflow.add_node("judge", judge_node)
        workflow.add_node("narrative_enrich", narrative_enrich_node)

        # Parallel synthesis branches
        workflow.add_node("chart_agent", chart_agent_node)
        workflow.add_node("section_writers", section_writers_node)
        workflow.add_node("exec_summary", exec_summary_node)

        # Fan-in assembler with defer=True to wait for parallel branches
        workflow.add_node("assembler", assembler_node, defer=True)
        workflow.add_node("chart_curator", chart_curator_node)

        # 2. Sequential Ingestion & Planning
        workflow.add_edge(START, "deterministic_ingest")
        workflow.add_edge("deterministic_ingest", "richness_assessor")
        workflow.add_edge("richness_assessor", "planner")
        workflow.add_edge("planner", "analyst_fanout")
        workflow.add_edge("analyst_fanout", "reflection")

        # 3. Conditional Reflection Route
        workflow.add_conditional_edges(
            "reflection",
            route_reflection,
            {
                "followup": "followup_analysis",
                "gather": "gather",
            },
        )
        workflow.add_edge("followup_analysis", "gather")

        # 4. Conditional Gather Route (Verify vs Judge Gate)
        workflow.add_conditional_edges(
            "gather",
            route_gather,
            {
                "verify": "verify",
                "judge": "judge",
            },
        )
        workflow.add_edge("verify", "judge")

        # 5. Narrative Enrichment
        workflow.add_edge("judge", "narrative_enrich")

        # 6. Parallel Fan-Out to Synthesis Branches
        workflow.add_edge("narrative_enrich", "chart_agent")
        workflow.add_edge("narrative_enrich", "section_writers")
        workflow.add_edge("narrative_enrich", "exec_summary")

        # 7. Fan-In to Assembler
        workflow.add_edge("chart_agent", "assembler")
        workflow.add_edge("section_writers", "assembler")
        workflow.add_edge("exec_summary", "assembler")

        # 8. Chart Curator & Publication
        workflow.add_edge("assembler", "chart_curator")
        workflow.add_edge("chart_curator", END)

        self.workflow = workflow
        return self

    def compile(self, checkpointer=None):
        """Compiles the StateGraph with the provided checkpointer."""
        if self.workflow is None:
            self.build()

        active_checkpointer = checkpointer or self.checkpointer
        self.compiled_graph = self.workflow.compile(checkpointer=active_checkpointer)
        logger.info("Stock Analysis StateGraph compiled successfully.")
        return self.compiled_graph

    def save_visualization(self, output_path: str = "app/static/stock_analysis_graph.png") -> None:
        """Saves visual PNG and Mermaid text definitions of the stock analysis graph."""
        from app.graphs.visualizer import export_graph_visualization

        if self.compiled_graph is None:
            self.compile()
        export_graph_visualization(self.compiled_graph, output_path=output_path)


def build_stock_analysis_graph(checkpointer=None):
    """Factory helper to build and compile the stock analysis graph."""
    return StockAnalysisGraphBuilder(checkpointer=checkpointer).compile()
