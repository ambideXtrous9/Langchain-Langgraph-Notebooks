"""Middleware Package for LangGraph and LangChain Agents.

Provides PII redaction, rate limiting, Human-in-the-loop interception, and conversation summarization.
"""

from app.middleware.base import AgentMiddleware, AgentMiddlewarePipeline
from app.middleware.pii import PIIMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, RateLimitExceededException
from app.middleware.hitl import HumanInTheLoopMiddleware, HumanApprovalRequiredException
from app.middleware.summarizer import SummarizationMiddleware

# Default Global Middleware Pipeline
default_agent_pipeline = AgentMiddlewarePipeline([
    RateLimitMiddleware(max_requests_per_window=60, window_seconds=60, max_consecutive_errors=3),
    PIIMiddleware(strategy="mask", pii_types=["email", "phone", "ssn", "credit_card", "medical_id"]),
    SummarizationMiddleware(trigger=[("tokens", 1200), ("messages", 8)], preserve_recent_count=3),
    HumanInTheLoopMiddleware(sensitive_tools=["execute_sql_mutation", "submit_compliance_audit", "delete_records"]),
])

__all__ = [
    "AgentMiddleware",
    "AgentMiddlewarePipeline",
    "PIIMiddleware",
    "RateLimitMiddleware",
    "RateLimitExceededException",
    "HumanInTheLoopMiddleware",
    "HumanApprovalRequiredException",
    "SummarizationMiddleware",
    "default_agent_pipeline",
]
