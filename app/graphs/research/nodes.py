"""Node Implementations for the Parallel Research, Critic, and Publisher Graph."""

import asyncio
import logging
from typing import Any, Dict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from app.core.config import settings
from app.core.llm import get_llm
from app.schemas.research import ApprovalDecision, ResearchState
from app.tools.duckduckgo import duckduckgo_search, format_search_results

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. Planner Node
# ------------------------------------------------------------------------------
async def planner_node(state: ResearchState) -> Dict[str, Any]:
    """Generates a structured research plan and targeted search queries."""
    topic = state.get("topic", "")
    critique = state.get("plan_critique", "")
    revision_count = state.get("plan_revision_count", 0)

    logger.info(f"[Planner] Generating plan for: '{topic}' (Revision: {revision_count})")

    prompt = (
        f"You are a Research Planner. Create a focused research strategy for:\n\nTopic: {topic}\n"
    )
    if critique:
        prompt += f"\nPrevious Approver Feedback:\n{critique}\n"

    prompt += (
        "\nProvide:\n"
        "1. Core Objective (2 sentences)\n"
        "2. Key Pillars (3 bullet points)\n"
        "3. 2-3 specific DuckDuckGo search queries (one per line starting with 'QUERY:')"
    )

    llm = get_llm(temperature=0.1, max_tokens=settings.PLANNER_MAX_TOKENS)
    response = await llm.ainvoke([
        SystemMessage(content="You are a strategic research planner. Be concise and structured."),
        HumanMessage(content=prompt),
    ])
    plan_text = response.content

    # Extract queries
    queries = []
    for line in plan_text.splitlines():
        if line.strip().startswith("QUERY:"):
            q = line.replace("QUERY:", "").strip()
            if q:
                queries.append(q)

    if not queries:
        queries = [
            f"{topic} overview guidelines",
            f"{topic} regulations best practices",
        ]

    return {
        "plan": plan_text,
        "research_queries": queries[:3],
        "plan_revision_count": revision_count + 1,
    }


# ------------------------------------------------------------------------------
# 2. Approver Agent Node (Autonomous Plan Reviewer)
# ------------------------------------------------------------------------------
async def approver_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Autonomous Approver Agent validating plan quality."""
    topic = state.get("topic", "")
    plan = state.get("plan", "")
    revision_count = state.get("plan_revision_count", 1)

    logger.info(f"[Approver Agent] Reviewing plan (Cycle: {revision_count})")

    if revision_count >= 2:
        return {
            "plan_approved": True,
            "plan_critique": "Plan approved for execution.",
        }

    prompt = (
        f"Evaluate this research plan for topic: '{topic}'\n\nPlan:\n{plan}\n\n"
        "Criteria: Clear scope, relevant search queries. Decide APPROVE or REVISION."
    )

    llm = get_llm(temperature=0.0, max_tokens=settings.APPROVER_MAX_TOKENS)
    structured_llm = llm.with_structured_output(ApprovalDecision)

    try:
        decision: ApprovalDecision = await structured_llm.ainvoke([
            SystemMessage(content="You are an editorial review agent."),
            HumanMessage(content=prompt),
        ])
        return {
            "plan_approved": decision.approved,
            "plan_critique": decision.critique,
        }
    except Exception:
        return {
            "plan_approved": True,
            "plan_critique": "Approved via validation.",
        }


# ------------------------------------------------------------------------------
# 3. Researcher Dispatcher Node
# ------------------------------------------------------------------------------
async def researcher_dispatcher_node(state: ResearchState) -> Dict[str, Any]:
    """Dispatches DuckDuckGo search queries."""
    topic = state.get("topic", "")
    queries = state.get("research_queries", [])

    if not queries:
        queries = [
            f"{topic} guidelines",
            f"{topic} key requirements",
        ]

    return {
        "research_queries": queries[:3],
    }


# ------------------------------------------------------------------------------
# 4. Researcher Node (Live DuckDuckGo Execution)
# ------------------------------------------------------------------------------
async def researcher_node(state: ResearchState) -> Dict[str, Any]:
    """Executes DuckDuckGo searches in parallel."""
    queries = state.get("research_queries", [])
    logger.info(f"[Researcher] Querying DuckDuckGo for {len(queries)} queries.")

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, duckduckgo_search, q, 3)
        for q in queries
    ]
    raw_results_list = await asyncio.gather(*tasks)

    formatted_notes = []
    for query, results in zip(queries, raw_results_list):
        note = format_search_results(results, query)
        formatted_notes.append(note)

    return {
        "research_notes": formatted_notes,
    }


# ------------------------------------------------------------------------------
# 5. Synthesizer Node (Drafting)
# ------------------------------------------------------------------------------
async def synthesizer_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesizes research notes into an initial draft."""
    topic = state.get("topic", "")
    plan = state.get("plan", "")
    notes = "\n\n".join(state.get("research_notes", []))

    logger.info(f"[Synthesizer] Drafting article on: '{topic}'")

    prompt = (
        f"You are a Senior Technical Author. Draft a concise, high-impact report.\n\n"
        f"Topic: {topic}\n\n"
        f"Outline:\n{plan}\n\n"
        f"Web Research Findings:\n{notes}\n\n"
        "Draft a structured 3-section article with clear headings, a summary table, and key takeaways."
    )

    llm = get_llm(temperature=0.1, max_tokens=settings.SYNTHESIZER_MAX_TOKENS)
    response = await llm.ainvoke([
        SystemMessage(content="You are a concise technical writer."),
        HumanMessage(content=prompt),
    ])

    return {
        "draft": response.content,
    }


# ------------------------------------------------------------------------------
# 6. Branch A: Fact Critic Node (Parallel Evaluation)
# ------------------------------------------------------------------------------
async def fact_critic_node(state: ResearchState) -> Dict[str, Any]:
    """Audits draft for factual accuracy and evidence."""
    draft = state.get("draft", "")
    notes = "\n\n".join(state.get("research_notes", []))

    logger.info("[Fact Critic] Auditing draft facts...")

    prompt = (
        f"Audit this draft against research notes.\n\nDraft:\n{draft}\n\nResearch Notes:\n{notes}\n\n"
        "List in 3-4 bullet points: Verified facts, potential discrepancies, and suggested corrections."
    )

    llm = get_llm(temperature=0.0, max_tokens=settings.FACT_CRITIC_MAX_TOKENS)
    response = await llm.ainvoke([
        SystemMessage(content="You are a strict technical fact auditor. Be concise."),
        HumanMessage(content=prompt),
    ])

    return {
        "fact_critique": response.content,
    }


# ------------------------------------------------------------------------------
# 7. Branch B - Step 1: Style Critic 1 Node (Parallel Evaluation)
# ------------------------------------------------------------------------------
async def style_critic_1_node(state: ResearchState) -> Dict[str, Any]:
    """Evaluates tone, clarity, and readability."""
    draft = state.get("draft", "")
    logger.info("[Style Critic 1] Evaluating tone and clarity...")

    prompt = (
        f"Evaluate tone, clarity, and sentence flow for this draft:\n\n{draft}\n\n"
        "Provide 3 concise bullet recommendations for improved readability and professional voice."
    )

    llm = get_llm(temperature=0.1, max_tokens=settings.STYLE_CRITIC_MAX_TOKENS)
    response = await llm.ainvoke([
        SystemMessage(content="You are an editorial clarity reviewer. Be concise."),
        HumanMessage(content=prompt),
    ])

    return {
        "style_critique_1": response.content,
    }


# ------------------------------------------------------------------------------
# 8. Branch B - Step 2: Style Critic 2 Node
# ------------------------------------------------------------------------------
async def style_critic_2_node(state: ResearchState) -> Dict[str, Any]:
    """Evaluates executive polish, formatting, and visual layout."""
    draft = state.get("draft", "")
    style_1 = state.get("style_critique_1", "")

    logger.info("[Style Critic 2] Evaluating executive formatting and layout...")

    prompt = (
        f"Building on style critique:\n{style_1}\n\nDraft:\n{draft}\n\n"
        "Provide 3 bullet recommendations for markdown tables, visual hierarchy, and actionable takeaways."
    )

    llm = get_llm(temperature=0.1, max_tokens=settings.STYLE_CRITIC_MAX_TOKENS)
    response = await llm.ainvoke([
        SystemMessage(content="You are an executive formatting reviewer. Be concise."),
        HumanMessage(content=prompt),
    ])

    return {
        "style_critique_2": response.content,
    }


# ------------------------------------------------------------------------------
# 9. Publisher Node (Fan-In with defer=True)
# ------------------------------------------------------------------------------
async def publisher_node(state: ResearchState) -> Dict[str, Any]:
    """Merges the draft with all parallel critiques into the finalized publication.

    Configured with `defer=True` in StateGraph to wait for all parallel branches to finish.
    """
    topic = state.get("topic", "")
    draft = state.get("draft", "")
    fact_critique = state.get("fact_critique", "")
    style_1 = state.get("style_critique_1", "")
    style_2 = state.get("style_critique_2", "")

    logger.info(f"[Publisher (defer=True)] Publishing final report for topic: '{topic}'")

    prompt = (
        f"You are the Chief Publisher. Produce the final polished report.\n\n"
        f"Topic: {topic}\n\n"
        f"Draft:\n{draft}\n\n"
        f"Fact Audit:\n{fact_critique}\n\n"
        f"Style & Tone Feedback:\n{style_1}\n\n"
        f"Executive & Layout Feedback:\n{style_2}\n\n"
        "Produce the complete, finalized publication in clean GitHub-flavored markdown with summary tables and key takeaways."
    )

    llm = get_llm(temperature=0.0, max_tokens=settings.PUBLISHER_MAX_TOKENS)
    response = await llm.ainvoke(
        [
            SystemMessage(content="You are the chief publisher releasing the final authoritative report."),
            HumanMessage(content=prompt),
        ],
        config={"tags": ["Publisher", "ResearchPublisher"]},
    )

    published_content = response.content

    return {
        "final_output": published_content,
        "messages": [AIMessage(content=published_content)],
    }
