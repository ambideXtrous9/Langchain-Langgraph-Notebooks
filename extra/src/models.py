from typing import Annotated, TypedDict, List
import operator
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage

# 1. Custom State: short/long-term memory + audit
class ProdAgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    customer_context: str                        # Persistent profile
    session_summary: str = ""                    # Auto-summarized memory
    confidence_scores: Annotated[List[float], operator.add] = []
    error_count: int = 0

# 2. Structured Output Schema
class AgentResponse(BaseModel):
    """Parsed agent decision."""
    intent: str = Field(..., description="user_intent: query|purchase|support")
    action: str = Field(..., description="tool|respond|escalate")
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = Field(..., max_length=500)
