"""Graph Builder for MCP Travel and Intelligence StateGraph."""

import logging
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from app.graphs.mcp.nodes import airbnb_agent_node, tour_guide_node, weather_agent_node
from app.schemas.mcp import MCPTravelState

logger = logging.getLogger(__name__)


class MCPTravelGraphBuilder:
    """Builder class for the MCP-integrated multi-agent travel state graph."""

    def __init__(self, checkpointer: Optional[BaseCheckpointSaver] = None) -> None:
        self.checkpointer = checkpointer

    def build_graph(self) -> CompiledStateGraph:
        """Constructs and compiles the concurrent fan-out / fan-in MCP travel graph."""
        logger.info("Assembling MCP Travel Multi-Agent Graph...")
        builder = StateGraph(MCPTravelState)

        # 1. Add Graph Nodes
        builder.add_node("airbnbAgent", airbnb_agent_node)
        builder.add_node("weatherAgent", weather_agent_node)
        builder.add_node("tourAgent", tour_guide_node)

        # 2. Parallel Fan-Out from START to concurrent agents
        builder.add_edge(START, "airbnbAgent")
        builder.add_edge(START, "weatherAgent")

        # 3. Fan-In to Tour Guide synthesis agent
        builder.add_edge("airbnbAgent", "tourAgent")
        builder.add_edge("weatherAgent", "tourAgent")

        # 4. Terminal edge
        builder.add_edge("tourAgent", END)

        # 5. Compile graph with optional checkpointer
        if self.checkpointer:
            compiled = builder.compile(checkpointer=self.checkpointer)
        else:
            compiled = builder.compile()

        logger.info("MCP Travel Multi-Agent Graph compiled successfully.")
        return compiled

    def get_mermaid_graph(self) -> str:
        """Generates Mermaid diagram definition of the compiled graph."""
        compiled = self.build_graph()
        return compiled.get_graph().draw_mermaid()


def create_mcp_travel_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> CompiledStateGraph:
    """Factory helper to instantiate and compile the MCP travel graph."""
    builder = MCPTravelGraphBuilder(checkpointer=checkpointer)
    return builder.build_graph()
