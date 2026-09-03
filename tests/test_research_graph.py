"""Unit and Integration Tests for the Parallel Research, Critic, and Publisher Graph."""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from app.graphs.research.builder import ResearchGraphBuilder, route_approver_decision
from app.tools.duckduckgo import format_search_results


def test_route_approver_decision():
    """Tests routing logic for the Approver Agent."""
    # 1. Approved -> 'dispatch'
    assert route_approver_decision({"plan_approved": True}) == "dispatch"

    # 2. Not approved -> 'revise'
    assert route_approver_decision({"plan_approved": False}) == "revise"
    assert route_approver_decision({}) == "revise"


def test_research_graph_compilation_and_topology():
    """Tests compilation, nodes, parallel branches, and defer=True configuration."""
    checkpointer = MemorySaver()
    builder = ResearchGraphBuilder(checkpointer=checkpointer)
    builder.build()
    graph = builder.compile()

    assert graph is not None
    expected_nodes = [
        "planner",
        "approver",
        "researcher_dispatcher",
        "researcher",
        "synthesizer",
        "fact_critic",
        "style_critic_1",
        "style_critic_2",
        "publisher",
    ]
    for node in expected_nodes:
        assert node in graph.nodes

    # Verify Mermaid output includes publisher defer=True
    mermaid_str = graph.get_graph().draw_mermaid()
    assert "publisher" in mermaid_str
    assert "defer = True" in mermaid_str
    assert "fact_critic" in mermaid_str
    assert "style_critic_1" in mermaid_str
    assert "style_critic_2" in mermaid_str


def test_format_search_results():
    """Tests search result markdown formatting."""
    results = [
        {"title": "Test ISO Standard", "body": "Guideline summary details", "href": "https://standards.org/test"}
    ]
    formatted = format_search_results(results, "Test Query")
    assert "Test Query" in formatted
    assert "Test ISO Standard" in formatted
    assert "https://standards.org/test" in formatted
