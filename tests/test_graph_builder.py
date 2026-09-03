"""Unit Tests for LangGraph StateGraph Construction and Routing Logic."""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from app.graphs.builder import GraphBuilder
from app.graphs.routing import decide_start_node


def test_routing_logic():
    """Tests conditional routing logic based on classification and device flags."""
    # 1. Exit classification -> 'end'
    assert decide_start_node({"classification": {"classification": "exit"}}) == "end"

    # 2. Generic chit-chat -> 'feedbackloop'
    assert decide_start_node({"classification": {"classification": "generic"}}) == "feedbackloop"

    # 3. Policy topic with system data -> 'device'
    assert (
        decide_start_node(
            {
                "classification": {"classification": "policy"},
                "useDeviceData": True,
                "userProvidedDeiveceData": "Kafka streaming model X",
            }
        )
        == "device"
    )

    # 4. Policy topic without system data -> 'knowledge'
    assert (
        decide_start_node(
            {
                "classification": {"classification": "policy"},
                "useDeviceData": False,
                "userProvidedDeiveceData": "",
            }
        )
        == "knowledge"
    )


def test_graph_compilation():
    """Tests StateGraph construction and compilation with in-memory checkpointer."""
    checkpointer = MemorySaver()
    builder = GraphBuilder(checkpointer=checkpointer)
    builder.build()
    compiled_graph = builder.compile()

    assert compiled_graph is not None
    assert "user_initpath" in compiled_graph.nodes
    assert "classify_node" in compiled_graph.nodes
    assert "reason_llm" in compiled_graph.nodes


def test_state_reducers():
    """Tests the state reducers: add_messages for messages and operator.add for lists."""
    import operator
    from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
    from langgraph.graph.message import add_messages

    # 1. Message reducer add_messages
    msgs = [HumanMessage(content="Hello", id="1")]
    updated_msgs = add_messages(msgs, [AIMessage(content="Hi there", id="2")])
    assert len(updated_msgs) == 2
    assert isinstance(updated_msgs[0], HumanMessage)
    assert isinstance(updated_msgs[1], AIMessage)

    # Message deduplication and removal
    updated_msgs2 = add_messages(updated_msgs, [RemoveMessage(id="1")])
    assert len(updated_msgs2) == 1
    assert updated_msgs2[0].id == "2"

    # 2. List reducer operator.add
    reviews_left = ["Review 1: Approved initial pathway"]
    reviews_right = ["Review 2: Clinical trial required"]
    merged_reviews = operator.add(reviews_left, reviews_right)
    assert len(merged_reviews) == 2
    assert merged_reviews[0] == "Review 1: Approved initial pathway"
    assert merged_reviews[1] == "Review 2: Clinical trial required"
