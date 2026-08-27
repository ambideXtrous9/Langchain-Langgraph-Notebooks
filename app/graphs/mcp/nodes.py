"""Graph nodes for MCP-powered Airbnb, Weather, and Tour Guide multi-agent system."""

import logging
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from app.core.config import settings
from app.core.llm import get_llm
from app.core.mcp import mcp_manager
from app.middleware import default_agent_pipeline
from app.schemas.mcp import MCPTravelState
from app.tools.weather import weather_forecast_tool

logger = logging.getLogger(__name__)

AIRBNB_AGENT_PROMPT = """You are an Airbnb Search Agent connected to the openbnb MCP server.

When invoking the airbnb_search tool:
- Extract and pass ONLY 'location' (e.g. 'Darjeeling, India') and 'adults' (e.g. 2).
- DO NOT pass cursor or optional null parameters.

**CRITICAL ACCURACY RULES:**
- DO NOT hallucinate fake property names, dollar prices, or fake room numbers (like rooms/12345678).
- If the tool returns parsed property IDs, display them with verified details.
- If the tool returns a searchUrl, extract the direct geocoded URL from the MCP tool and prominently present it: `[Search Live Accommodations on Airbnb](<searchUrl>)`.
- Give practical guidance on filters (Entire place, Scenic view, Superhost) and local price expectations.

## 🎯 Search Summary
- **Location:** [Location]
- **Guests:** [adults] Adults
- **Live Search Link:** [Explore Stays on Airbnb](<searchUrl>)

## 🏨 Accommodation Overview & Direct Search
- **Geocoded Search Link:** [Search Live Accommodations on Airbnb](<searchUrl>)
- **Search Parameters Applied:** Destination resolved with bounding coordinates and guest configuration.
- **Booking Guidance:** Recommended neighborhoods, filters (e.g., heating, mountain view, Superhost), and tips for the destination.
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

TOUR_AGENT_PROMPT = """You are a Master Travel & Tour Guide Assistant. Synthesize a comprehensive travel plan based on the destination query, the Airbnb MCP report, and the Weather report.

**CRITICAL ACCURACY & LINK RULES:**
- DO NOT invent fake individual hotel names or non-existent room numbers (like rooms/12345678).
- Extract and prominently display the real geocoded Airbnb search URL from the Airbnb report: `[Search Live Accommodations on Airbnb](<searchUrl>)`.
- Synthesize the real meteorological forecast into tailored weather recommendations, packing tips, and day-by-day itineraries.

---

## 🎯 Travel Summary
- **Destination:** [Destination]
- **Guests:** [Guests]
- **Verified Airbnb Search:** [Search Live Accommodations on Airbnb](<searchUrl>)

---

## 🏨 Accommodation & Stay Strategy
- **Direct Airbnb Filtered Search:** [Open Live Airbnb Search for <Destination>](<searchUrl>)
- **Recommended Neighborhoods:** [Best areas for mountain views, tranquility, or central access]
- **Key Filter Recommendations:** [Cottage/Entire Place, Heating, Scenic View, Superhost]

---

## 🌤️ 3-Day Weather Forecast & Activity Plan
- **Current Conditions:** [Current temperature and condition from weather report]
- **Forecast Outlook:** [Day 1, Day 2, Day 3 summary]
- **Weather Recommendation:** [Clothing and outdoor/indoor activity match]

---

## 🧭 Curated Itinerary & Travel Advisory
- **Suggested Itinerary:** [Day 1, Day 2, Day 3 highlights]
- **Clothing Advice:** [Recommended layers/footwear]
- **Safety & Packing:** [Key essentials]

---

### 🌟 Local Insight & Travel Tip
[Special local travel tip, dining gem, or scenic route]
---
"""


async def airbnb_agent_node(state: MCPTravelState) -> Dict[str, Any]:
    """Node that queries MCP tools via MultiServerMCPClient and formats an accommodation report."""
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
        "knowledge": [HumanMessage(content=f"[Info from AirBnb Search]\n{ai_content}\n\n")],
    }


# Alias for direct invocation
airbnbAgent = airbnb_agent_node


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
    """Fan-in node that synthesizes Airbnb and Weather intelligence into a final tour guide plan."""
    logger.info("Executing Tour Guide synthesis node...")
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
