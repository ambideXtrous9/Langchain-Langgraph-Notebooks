"""Comprehensive Unit & Integration Tests for Agent Middleware Suite."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.middleware.base import AgentMiddlewarePipeline
from app.middleware.pii import PIIMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, RateLimitExceededException
from app.middleware.hitl import HumanInTheLoopMiddleware, HumanApprovalRequiredException
from app.middleware.summarizer import SummarizationMiddleware, estimate_token_count


# ==============================================================================
# 1. PII Guard Middleware Tests
# ==============================================================================

def test_pii_middleware_mask_strategy():
    """Tests PII masking for emails, phones, SSNs, and medical record numbers."""
    pii = PIIMiddleware(strategy="mask")

    raw_text = (
        "Contact investigator dr.smith@fda-trial.gov at +1 (555) 234-5678. "
        "Patient SSN is 123-45-6789 and Medical ID is MRN:REC-987654."
    )
    sanitized = pii.sanitize_text(raw_text)

    assert "[EMAIL_REDACTED]" in sanitized
    assert "dr.smith@fda-trial.gov" not in sanitized
    assert "[PHONE_REDACTED]" in sanitized
    assert "(555) 234-5678" not in sanitized
    assert "[SSN_REDACTED]" in sanitized
    assert "123-45-6789" not in sanitized
    assert "[MEDICAL_ID_REDACTED]" in sanitized
    assert "REC-987654" not in sanitized


def test_pii_middleware_redact_and_hash_strategies():
    """Tests PII redaction and SHA-256 hashing strategies."""
    redact_pii = PIIMiddleware(strategy="redact")
    assert redact_pii.sanitize_text("user@domain.com") == "***"

    hash_pii = PIIMiddleware(strategy="hash")
    hashed = hash_pii.sanitize_text("user@domain.com")
    assert "[EMAIL_HASH:" in hashed
    assert "user@domain.com" not in hashed


@pytest.mark.asyncio
async def test_pii_middleware_message_hooks():
    """Tests PII scrubbing on LangChain messages in before_model and after_model."""
    pii = PIIMiddleware(strategy="mask")

    messages = [
        SystemMessage(content="System prompt without PII"),
        HumanMessage(content="My email is patient.doe@hospital.org and phone is 555-123-4567"),
    ]

    state, sanitized_messages = await pii.before_model({}, messages)
    assert "[EMAIL_REDACTED]" in sanitized_messages[1].content
    assert "[PHONE_REDACTED]" in sanitized_messages[1].content
    assert "patient.doe@hospital.org" not in sanitized_messages[1].content

    # Output sanitization in after_model
    ai_leak_response = AIMessage(content="I have recorded patient.doe@hospital.org in the database.")
    _, clean_response = await pii.after_model(state, ai_leak_response)
    assert "[EMAIL_REDACTED]" in clean_response.content
    assert "patient.doe@hospital.org" not in clean_response.content


# ==============================================================================
# 2. Rate Limiter Middleware Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limit_middleware_sliding_window():
    """Tests that RateLimitMiddleware raises RateLimitExceededException when limit is exceeded."""
    limiter = RateLimitMiddleware(max_requests_per_window=3, window_seconds=2)
    state = {"thread_id": "test_user_rate_limit"}

    # 3 allowed requests
    await limiter.before_agent(state)
    await limiter.before_agent(state)
    await limiter.before_agent(state)

    # 4th request must raise RateLimitExceededException
    with pytest.raises(RateLimitExceededException) as exc_info:
        await limiter.before_agent(state)

    assert "Rate limit" in str(exc_info.value)
    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_rate_limit_middleware_error_budget_and_confidence():
    """Tests consecutive error tracking and confidence monitoring."""
    limiter = RateLimitMiddleware(max_consecutive_errors=2, min_confidence_threshold=0.7)
    key = "user_circuit_test"

    assert limiter.record_error(key) == 1
    assert limiter.record_error(key) == 2

    state = {"user_id": key, "confidence": 0.45}
    state = await limiter.before_agent(state)
    assert state.get("circuit_breaker_active") is True

    # After valid model return, confidence flag is set and errors reset
    state, _ = await limiter.after_model(state, "model response")
    assert state.get("low_confidence_flag") is True
    assert limiter.get_error_count(key) == 0


# ==============================================================================
# 3. Human In The Loop Middleware Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_hitl_middleware_state_flagging():
    """Tests that sensitive tools trigger human approval state flags."""
    hitl = HumanInTheLoopMiddleware(sensitive_tools=["execute_sql_mutation", "override_inventory"])

    state = {}
    tool_calls = [
        {"name": "fetch_fda_guidance", "args": {"topic": "catheter"}},
        {"name": "execute_sql_mutation", "args": {"query": "DROP TABLE audit_logs;"}},
    ]

    updated_state, remaining_tools = await hitl.before_tools(state, tool_calls)
    assert updated_state.get("human_approval_required") is True
    assert updated_state["pending_sensitive_tool"]["name"] == "execute_sql_mutation"


@pytest.mark.asyncio
async def test_hitl_middleware_exception_trigger():
    """Tests that HumanApprovalRequiredException is raised when configured."""
    hitl = HumanInTheLoopMiddleware(
        sensitive_tools=["delete_records"],
        raise_exception_on_trigger=True,
    )

    state = {}
    tool_calls = [{"name": "delete_records", "args": {"record_id": "REC-1234"}}]

    with pytest.raises(HumanApprovalRequiredException) as exc_info:
        await hitl.before_tools(state, tool_calls)

    assert "delete_records" in str(exc_info.value)
    assert exc_info.value.tool_args == {"record_id": "REC-1234"}


# ==============================================================================
# 4. Summarization Middleware Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_summarization_middleware_message_trigger():
    """Tests message compression when message count threshold is crossed."""
    summarizer = SummarizationMiddleware(
        trigger=[("messages", 5)],
        preserve_recent_count=2,
    )

    messages = [
        SystemMessage(content="You are an FDA Regulatory Expert."),
        HumanMessage(content="Device A is a Class II dental drill."),
        AIMessage(content="510(k) pathway is recommended."),
        HumanMessage(content="Device B is an implantable pacemaker."),
        AIMessage(content="PMA pathway is recommended."),
        HumanMessage(content="What about Device C?"),
    ]

    state, compressed = await summarizer.before_model({}, messages)

    assert state.get("messages_summarized") is True
    # Should contain: SystemMessage + Summary SystemMessage + last 2 messages = 4 messages
    assert len(compressed) == 4
    assert isinstance(compressed[0], SystemMessage)
    assert "[Context Summary" in compressed[1].content
    assert compressed[2].content == "PMA pathway is recommended."
    assert compressed[3].content == "What about Device C?"


# ==============================================================================
# 5. Agent Middleware Pipeline End-to-End Test
# ==============================================================================

@pytest.mark.asyncio
async def test_middleware_pipeline_full_chain():
    """Tests full pipeline integration combining RateLimiting, PII, Summarization, and HITL."""
    pipeline = AgentMiddlewarePipeline([
        RateLimitMiddleware(max_requests_per_window=10, window_seconds=60),
        PIIMiddleware(strategy="mask"),
        SummarizationMiddleware(trigger=[("messages", 4)], preserve_recent_count=2),
        HumanInTheLoopMiddleware(sensitive_tools=["submit_fda_filing"]),
    ])

    # 1. before_agent hook
    state = {
        "user_id": "dr_smith",
        "user_input": "My email is dr.smith@clinic.com. Filing for device.",
    }
    state = await pipeline.run_before_agent(state)
    assert "[EMAIL_REDACTED]" in state["user_input"]

    # 2. before_model hook
    messages = [
        HumanMessage(content="Query 1 from dr.smith@clinic.com"),
        AIMessage(content="Response 1"),
        HumanMessage(content="Query 2"),
        AIMessage(content="Response 2"),
        HumanMessage(content="Query 3"),
    ]
    state, clean_messages = await pipeline.run_before_model(state, messages)
    assert state.get("messages_summarized") is True

    # 3. before_tools hook
    tool_calls = [{"name": "submit_fda_filing", "args": {"docket": "FDA-2026"}}]
    state, _ = await pipeline.run_before_tools(state, tool_calls)
    assert state.get("human_approval_required") is True

    # 4. after_model hook
    state, response = await pipeline.run_after_model(
        state,
        AIMessage(content="Contact support at help@fda.gov for docket info.")
    )
    assert "[EMAIL_REDACTED]" in response.content
