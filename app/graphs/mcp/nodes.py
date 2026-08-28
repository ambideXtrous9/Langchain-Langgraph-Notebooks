"""Graph nodes for MCP-powered Harry Potter Universe QA and Airbnb Travel multi-agent system."""

import logging
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from app.core.config import settings
from app.core.llm import get_llm
from app.core.mcp import mcp_manager
from app.middleware import default_agent_pipeline
from app.schemas.mcp import MCPTravelState
from app.tools.pinecone_tools import pinecone_index_stats, pinecone_multihop_search
from app.tools.weather import weather_forecast_tool

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. HARRY POTTER UNIVERSE QA PROMPTS & NODES (Mode: harry_potter)
# ==============================================================================

HP_SEARCH_AGENT_PROMPT = """You are an Autonomous Harry Potter Knowledge Retrieval Agent with access to the 7-book Harry Potter vector database (`hpvdb-openai`) via Pinecone MCP tools.

### 🛠️ AVAILABLE TOOLS:
- `search-records`: Primary semantic vector search on `hpvdb-openai` using natural language queries, metadata filters, and top-k limits.
- `pinecone_multihop_search`: Multi-hop sequential search across logical investigation stages.
- `cascading-search`: Cross-index or federated vector search across namespaces.
- `rerank-documents`: Cross-encoder model to re-score candidate passages when you have multiple search results.
- `describe-index-stats` / `describe-index` / `list-indexes`: Index schema and stats inspection (use ONLY when you specifically need index metadata).
- `search-docs`: Pinecone syntax documentation (use ONLY if you need help with filter syntax).

### 🧠 AUTONOMOUS REASONING & TOOL SELECTION RULES:
1. **Dynamic, Non-Deterministic Decisions**:
   - There is NO fixed sequence of steps. You decide which tools to call, in what order, how many times, or whether to skip any tools based purely on the specific user query.
   - Do NOT run unnecessary diagnostic tools (like `list-indexes` or `describe-index-stats`) unless your reasoning genuinely requires them.
   - If a simple, single search on `search-records` answers the question, you can stop immediately.

2. **Iterative Multi-Hop Reasoning (When Needed)**:
   - For multi-hop questions (e.g. tracing Horcrux creation & destruction, the Elder Wand lineage, or battle timelines), call `search-records` iteratively:
     - Hop 1: Search for the initial entity or origin.
     - Hop 2+: Analyze the retrieved text, extract new clues/characters, and execute follow-up searches to trace the causal chain.
   - You can call `search-records` multiple times with different targeted queries.

3. **Adaptive Reranking**:
   - Call `rerank-documents` if you have multiple candidate passages and need to isolate the most relevant canonical evidence.

4. **Smart Stopping Condition**:
   - Stop calling tools as soon as you have gathered enough verified canonical book excerpts from `hpvdb-openai` to answer the question completely.
   - Output a clear summary of the retrieved passages, book citations, and causal connections.
"""

HP_LORE_SCHOLAR_PROMPT = """You are the **Master Harry Potter Lore Scholar & Chronicler**. Your purpose is to provide authoritative, beautifully written, and deeply accurate answers to questions about the Harry Potter universe based STRICTLY on the retrieved Pinecone vector records and canonical book evidence.

Guidelines:
- Carefully review the retrieved passages and reasoning trace from `hpvdb-openai`.
- Walk the reader through the full causal chain step-by-step (e.g. chronological progression, wandlore mechanics, Horcrux creation & destruction sequence, or character relationships).
- Quote directly from the retrieved book passages with exact book citations.
- Clearly explain the magical rules, subtleties, character motives, and canonical nuances.
- DO NOT invent non-canonical facts or external movie-only additions without clarifying book canon.

**STRUCTURE YOUR RESPONSE CLEANLY:**

# ⚡ [Comprehensive Title Answering the Question]

## 📜 Canonical Overview & Direct Answer
[Clear, authoritative direct summary answering the question completely]

## 🔗 Chronological & Causal Analysis
- **Phase 1: Origins & Foundations:** [Foundational lore with book citations]
- **Phase 2: Pivotal Turning Points & Transitions:** [Middle transitions with character actions]
- **Phase 3: Climax & Canonical Resolution:** [Final resolution and magical mechanics]

## 📖 Book Excerpts & Direct Citations
> "[Direct quote from retrieved Pinecone records]"
> &mdash; *[Book Title, e.g., Harry Potter and the Deathly Hallows]*

## 💡 Scholarly Secrets & Wandlore Insights
[Subtle canonical foreshadowing, wandlore rules, and connections across the 7 books]
"""


async def hp_search_node(state: MCPTravelState) -> Dict[str, Any]:
    """Node agent executing autonomous Pinecone retrieval using LLM-chosen tools."""
    logger.info("Executing Autonomous Harry Potter Vector Retrieval Agent node with Pinecone MCP...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")

    llm = get_llm(max_tokens=settings.HP_AGENT_MAX_TOKENS)
    
    # 1. Gather all MCP tools from MultiServerMCPClient
    mcp_tools = await mcp_manager.get_tools()
    
    # 2. Add native Pinecone multi-hop search and stats tools
    all_hp_tools = list(mcp_tools) + [pinecone_multihop_search, pinecone_index_stats]

    try:
        agent = create_react_agent(
            model=llm,
            tools=all_hp_tools,
            prompt=HP_SEARCH_AGENT_PROMPT,
        )

        hp_query = (
            f"User Question: '{topic}'\n\n"
            "Please investigate this question using the Harry Potter vector database ('hpvdb-openai'). "
            "Use your reasoning to choose which tools to call, how many searches to perform, or which tools to skip. "
            "Gather and provide the canonical book evidence to answer the question accurately."
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": hp_query}]})
        ai_content = response["messages"][-1].content
    except Exception as exc:
        logger.error(f"Error in Multi-Hop Harry Potter Search Agent execution: {exc}", exc_info=True)
        ai_content = f"Error querying Harry Potter Pinecone vector database: {exc}"

    # Execute middleware after model
    _, ai_content = await default_agent_pipeline.run_after_model(state_dict, ai_content)

    return {
        "hp_report": ai_content,
        "knowledge": [HumanMessage(content=f"[Multi-Hop Info from Harry Potter Pinecone Vector DB]\n{ai_content}\n\n")],
    }


async def hp_lore_scholar_node(state: MCPTravelState) -> Dict[str, Any]:
    """Scholar node that synthesizes multi-hop Pinecone vector passages into an authoritative Harry Potter answer."""
    logger.info("Executing Harry Potter Lore Scholar synthesis node...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")
    knowledge = state.get("knowledge", [])
    hp_rep = state.get("hp_report", "")

    context = (
        f"User Question: {topic}\n\n"
        f"=== MULTI-HOP RETRIEVED HARRY POTTER PINECONE VECTOR RECORDS ===\n{hp_rep}\n\n"
        f"=== ALL COLLECTED KNOWLEDGE ===\n"
        + "\n".join([m.content if hasattr(m, "content") else str(m) for m in knowledge])
    )

    llm = get_llm(max_tokens=settings.HP_AGENT_MAX_TOKENS).with_config(tags=["HPLoreScholar"])

    response = await llm.ainvoke([
        SystemMessage(content=HP_LORE_SCHOLAR_PROMPT),
        HumanMessage(content=context),
    ])

    summary_text = response.content
    if isinstance(summary_text, list):
        summary_text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in summary_text])

    # Run after_model and after_agent middleware hooks
    _, summary_text = await default_agent_pipeline.run_after_model(state_dict, summary_text)
    state_dict["summary"] = summary_text
    state_dict = await default_agent_pipeline.run_after_agent(state_dict)

    return {"summary": state_dict.get("summary", summary_text)}


# Aliases for HP mode
hpSearchAgent = hp_search_node
hpLoreScholar = hp_lore_scholar_node
hpAgent = hp_search_node
harry_potter_agent_node = hp_search_node


# ==============================================================================
# 2. AIRBNB TRAVEL & LODGING PROMPTS & NODES (Mode: airbnb)
# ==============================================================================

AIRBNB_AGENT_PROMPT = """You are an Airbnb Search Agent connected to the openbnb MCP server.

When invoking the airbnb_search tool:
- Extract and pass ONLY 'location' (e.g. 'Edinburgh, Scotland' or 'Darjeeling, India') and 'adults' (e.g. 2).
- DO NOT pass cursor or optional null parameters.

**CRITICAL ACCURACY RULES:**
- DO NOT hallucinate fake property names, dollar prices, or fake room numbers (like rooms/12345678).
- If the tool returns parsed property IDs, display them with verified details.
- If the tool returns a searchUrl, extract the direct geocoded URL from the MCP tool and prominently present it: `[Search Live Accommodations on Airbnb](<searchUrl>)`.
- Give practical guidance on filters (Entire place, Scenic view, Superhost, Castle/Cottage) and local price expectations.

## 🎯 Search Summary
- **Location:** [Location]
- **Guests:** [adults] Adults
- **Live Search Link:** [Explore Stays on Airbnb](<searchUrl>)

## 🏨 Accommodation Overview & Direct Search
- **Geocoded Search Link:** [Search Live Accommodations on Airbnb](<searchUrl>)
- **Search Parameters Applied:** Destination resolved with bounding coordinates and guest configuration.
- **Booking Guidance:** Recommended neighborhoods, filters (e.g., heating, mountain view, historic charm, Superhost), and stay tips.
"""

WEATHER_AGENT_PROMPT = """You are a Weather & Meteorology Assistant.

- Extract the target travel destination from the query and immediately use the **WeatherForecast tool** to fetch the forecast.
- Then generate a **Weather Report** strictly following the Markdown format below.
- Do not add extra sections outside the format.

## Weather Report for <Location> (Next 3 Days)

**Current Conditions:** <CurrentTemp>°C with <CurrentCondition>

**Forecast Summary:**
- **Day 1:** <Condition>, <MaxTemp>°C / <MinTemp>°C
- **Day 2:** <Condition>, <MaxTemp>°C / <MinTemp>°C
- **Day 3:** <Condition>, <MaxTemp>°C / <MinTemp>°C

**Tour Recommendation:**
Based on the weather forecast, state clearly if it is a good time to visit <Location>.
Give practical advice: clothing, precautions, indoor/outdoor activity suggestions.
"""

TOUR_AGENT_PROMPT = """You are the **Master Travel & Tour Guide Assistant**. Synthesize a comprehensive travel, accommodation, and adventure plan based on:
1. The **Airbnb Accommodation Report** (lodgings, cottages, and live search links)
2. The **Weather Forecast Report** (3-day meteorological conditions and clothing tips)

**CRITICAL ACCURACY & LINK RULES:**
- DO NOT invent fake individual hotel names or non-existent room numbers.
- Extract and prominently display the real geocoded Airbnb search URL from the Airbnb report: `[Search Live Accommodations on Airbnb](<searchUrl>)`.
- Match clothing and outdoor activity advice with the real weather forecast.

---

## 🎯 Travel & Stay Summary
- **Destination:** [Destination]
- **Travelers:** [Guests / Party]
- **Verified Airbnb Search:** [Search Live Accommodations on Airbnb](<searchUrl>)

---

## 🏨 Accommodation & Stay Strategy
- **Direct Airbnb Filtered Search:** [Open Live Airbnb Search for <Destination>](<searchUrl>)
- **Recommended Neighborhoods & Stays:** [Cottages, manor stays, or mountain chalets]
- **Key Amenities & Filters:** [Cottage/Entire Place, Fireplace/Heating, Scenic View, Superhost]

---

## 🌤️ 3-Day Weather Forecast & Activity Plan
- **Current Conditions:** [Current temp and conditions]
- **Forecast Outlook:** [Day 1, Day 2, Day 3 conditions & temps]
- **Atmospheric Recommendation:** [Clothing layers and indoor/outdoor match]

---

## 🧭 Curated Itinerary & Travel Advisory
- **Day 1 (Arrival & Exploration):** [Activity]
- **Day 2 (Adventure & Sightseeing):** [Activity]
- **Day 3 (Leisure & Departure):** [Activity]

---

### 🌟 Local Insight & Hidden Gem
[Hidden gems, atmospheric dining, scenic viewpoints, or travel secrets]
---
"""


async def airbnb_agent_node(state: MCPTravelState) -> Dict[str, Any]:
    """Node that queries Airbnb MCP tools via MultiServerMCPClient and formats an accommodation report."""
    logger.info("Executing Airbnb Agent node with MultiServerMCPClient...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")

    llm = get_llm(max_tokens=settings.AIRBNB_AGENT_MAX_TOKENS)
    tools = await mcp_manager.get_tools()

    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=AIRBNB_AGENT_PROMPT,
        )

        response = await agent.ainvoke({"messages": [{"role": "user", "content": topic}]})
        ai_content = response["messages"][-1].content
    except Exception as exc:
        logger.error(f"Error in Airbnb Agent execution: {exc}")
        ai_content = f"Error retrieving Airbnb listings: {exc}"

    # Execute middleware after model
    _, ai_content = await default_agent_pipeline.run_after_model(state_dict, ai_content)

    return {
        "airbnb_report": ai_content,
        "knowledge": [HumanMessage(content=f"[Info from Airbnb Search]\n{ai_content}\n\n")],
    }


async def weather_agent_node(state: MCPTravelState) -> Dict[str, Any]:
    """Node that queries the Weather tool and formats a meteorological report."""
    logger.info("Executing Weather Agent node...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")

    llm = get_llm(max_tokens=settings.WEATHER_AGENT_MAX_TOKENS)
    agent = create_react_agent(
        model=llm,
        tools=[weather_forecast_tool],
        prompt=WEATHER_AGENT_PROMPT,
    )

    weather_query = (
        f"Travel Query: '{topic}'\n\n"
        "Instructions: Extract the destination location (city/region) and fetch the 3-day weather forecast using the WeatherForecast tool. "
        "Generate the complete weather report."
    )

    try:
        response = await agent.ainvoke({"messages": [{"role": "user", "content": weather_query}]})
        ai_content = response["messages"][-1].content
    except Exception as exc:
        logger.error(f"Error in Weather Agent execution: {exc}")
        ai_content = f"Error retrieving weather forecast: {exc}"

    # Execute middleware after model
    _, ai_content = await default_agent_pipeline.run_after_model(state_dict, ai_content)

    return {
        "weather_report": ai_content,
        "knowledge": [HumanMessage(content=f"[Info from Weather Search]\n{ai_content}\n\n")],
    }


async def tour_guide_node(state: MCPTravelState) -> Dict[str, Any]:
    """Fan-in node that synthesizes Airbnb accommodation and Weather into a master plan."""
    logger.info("Executing Master Tour Guide synthesis node...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")
    knowledge = state.get("knowledge", [])
    airbnb_rep = state.get("airbnb_report", "")
    weather_rep = state.get("weather_report", "")

    context = (
        f"User Query: {topic}\n\n"
        f"=== AIRBNB & ACCOMMODATION INTELLIGENCE ===\n{airbnb_rep}\n\n"
        f"=== WEATHER INTELLIGENCE ===\n{weather_rep}\n\n"
        f"=== ALL COLLECTED KNOWLEDGE ===\n"
        + "\n".join([m.content if hasattr(m, "content") else str(m) for m in knowledge])
    )

    llm = get_llm(max_tokens=settings.TOUR_AGENT_MAX_TOKENS).with_config(tags=["TourGuideExpert"])

    response = await llm.ainvoke([
        SystemMessage(content=TOUR_AGENT_PROMPT),
        HumanMessage(content=context),
    ])

    summary_text = response.content
    if isinstance(summary_text, list):
        summary_text = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in summary_text])

    # Run after_model and after_agent middleware hooks
    _, summary_text = await default_agent_pipeline.run_after_model(state_dict, summary_text)
    state_dict["summary"] = summary_text
    state_dict = await default_agent_pipeline.run_after_agent(state_dict)

    return {"summary": state_dict.get("summary", summary_text)}


# Aliases for Airbnb mode
airbnbAgent = airbnb_agent_node
weatherAgent = weather_agent_node
tourAgent = tour_guide_node

