"""Graph Builder for MCP Harry Potter Universe QA and Airbnb Multi-Agent StateGraphs."""

import logging
import os
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from app.graphs.mcp.nodes import (
    airbnb_agent_node,
    hp_lore_scholar_node,
    hp_search_node,
    tour_guide_node,
    weather_agent_node,
)
from app.schemas.mcp import MCPTravelState

logger = logging.getLogger(__name__)


class MCPTravelGraphBuilder:
    """Builder class for MCP multi-agent state graphs (supports 'harry_potter' and 'airbnb' modes)."""

    def __init__(self, checkpointer: Optional[BaseCheckpointSaver] = None) -> None:
        self.checkpointer = checkpointer

    def build_hp_graph(self) -> CompiledStateGraph:
        """Constructs and compiles the Harry Potter Universe QA graph via Pinecone MCP."""
        logger.info("Assembling MCP Harry Potter Universe QA Graph...")
        builder = StateGraph(MCPTravelState)

        # 1. Add Nodes
        builder.add_node("hpSearchAgent", hp_search_node)
        builder.add_node("hpLoreScholar", hp_lore_scholar_node)

        # 2. Sequential pipeline: START -> hpSearchAgent -> hpLoreScholar -> END
        builder.add_edge(START, "hpSearchAgent")
        builder.add_edge("hpSearchAgent", "hpLoreScholar")
        builder.add_edge("hpLoreScholar", END)

        if self.checkpointer:
            return builder.compile(checkpointer=self.checkpointer)
        return builder.compile()

    def build_airbnb_graph(self) -> CompiledStateGraph:
        """Constructs and compiles the Airbnb Accommodations & Weather fan-out / fan-in graph."""
        logger.info("Assembling MCP Airbnb Travel Multi-Agent Graph...")
        builder = StateGraph(MCPTravelState)

        # 1. Add Nodes (defer=True on tourAgent to ensure both parallel branches complete)
        builder.add_node("airbnbAgent", airbnb_agent_node)
        builder.add_node("weatherAgent", weather_agent_node)
        builder.add_node("tourAgent", tour_guide_node, defer=True)

        # 2. Parallel fan-out
        builder.add_edge(START, "airbnbAgent")
        builder.add_edge(START, "weatherAgent")

        # 3. Fan-in to Tour Guide
        builder.add_edge("airbnbAgent", "tourAgent")
        builder.add_edge("weatherAgent", "tourAgent")

        # 4. Terminal edge
        builder.add_edge("tourAgent", END)

        if self.checkpointer:
            return builder.compile(checkpointer=self.checkpointer)
        return builder.compile()

    def build_graph(self, mode: str = "harry_potter") -> CompiledStateGraph:
        """Builds the compiled graph based on the specified mode ('harry_potter' or 'airbnb')."""
        if mode == "airbnb":
            return self.build_airbnb_graph()
        return self.build_hp_graph()

    def get_mermaid_graph(self, mode: str = "harry_potter") -> str:
        """Generates Mermaid diagram definition for the specified mode."""
        compiled = self.build_graph(mode=mode)
        return compiled.get_graph().draw_mermaid()

    def save_visualization(self, output_path: str = "app/static/mcp_graph.png") -> None:
        """Saves visual representations of both MCP sub-graphs to disk."""
        from app.graphs.visualizer import export_graph_visualization

        hp_graph = self.build_hp_graph()
        airbnb_graph = self.build_airbnb_graph()
        export_graph_visualization(hp_graph, output_path.replace(".png", "_hp.png"))
        export_graph_visualization(airbnb_graph, output_path.replace(".png", "_airbnb.png"))
        export_graph_visualization(hp_graph, output_path)


def create_mcp_travel_graph(mode: str = "harry_potter", checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Factory helper to instantiate and compile the MCP graph for the selected mode."""
    builder = MCPTravelGraphBuilder(checkpointer=checkpointer)
    return builder.build_graph(mode=mode)


def create_hp_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Factory helper to instantiate the Harry Potter QA graph."""
    builder = MCPTravelGraphBuilder(checkpointer=checkpointer)
    return builder.build_hp_graph()


def create_airbnb_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Factory helper to instantiate the Airbnb search graph."""
    builder = MCPTravelGraphBuilder(checkpointer=checkpointer)
    return builder.build_airbnb_graph()

