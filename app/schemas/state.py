"""State Definitions and Reducers for LangGraph aligned with official LangGraph standards."""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages


class Classify(BaseModel):
    """Pydantic model for topic classification and immediate replies."""

    classification: Literal["generic", "fda", "exit"] = Field(
        description="Classify the topic type: 'generic' or 'fda' or 'exit'"
    )
    reply: str = Field(
        description=(
            "If 'generic', a natural language reply to the query. "
            "If 'fda', respond with 'FDA'. If 'exit', respond with 'exit'."
        )
    )


class AgentState(MessagesState, total=False):
    """Complete LangGraph AgentState representing graph execution context.

    Directly inherits from LangGraph's standard `MessagesState` which provides:
    - `messages: Annotated[list[AnyMessage], add_messages]` natively.

    Additional state fields & reducers:
    - `chat_history: Annotated[list[AnyMessage], add_messages]`
    - `reviews: Annotated[list[str], operator.add]`
    """

    tree: List[Dict[str, Any]]
    user_choices: Dict[str, Any]
    current_path_str: str
    user_decisions_str: str
    context_docs_str: str
    classification: Dict[str, Any]
    feedback: str
    useDeviceData: bool
    userProvidedDeiveceData: str
    chat_history: Annotated[List[AnyMessage], add_messages]
    reviews: Annotated[List[str], operator.add]
