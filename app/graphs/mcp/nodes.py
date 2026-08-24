"""Graph nodes for MCP-powered Airbnb, Weather, and Tour Guide multi-agent system."""

import logging
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from app.core.config import settings
from app.core.llm import get_llm
from app.core.mcp import mcp_manager
from app.middleware import default_agent_pipeline
from app.schemas.mcp import MCPTravelState
from app.tools.weather import weather_forecast_tool

logger = logging.getLogger(__name__)

AIRBNB_AGENT_PROMPT = """You are an Airbnb & Accommodation Assistant.

- Use the available accommodation search tools to find stays matching the user query.
- Generate an **ADVANCED HOTEL & AIRBNB REPORT** strictly following the markdown format below.

## 🎯 Search Summary
- **Location:** [location] | **Dates:** [checkin] → [checkout]
- **Guests:** [adults]A, [children]C, [infants]I, [pets]P
- **Room:** [room type] | **Stars:** [rating] | **Amenities:** [amenities]
- **Results:** [number] hotels/stays

## 🏨 Hotel & Airbnb Listings
### [Property Name]
| Detail | Info |
|--------|------|
| ⭐ Rating | [rating]/5 ([reviews]) |
| 📍 Address | [full address] |
| 💰 Rate | $[price]/night (+$[tax]) |
| 🏠 Rooms | [categories] |
| 📏 Distance | [city center] • [airport] |
| 🔗 Booking | [URL] |
| 📞 Contact | [phone] • [website] |

**Amenities:** [pool/gym/spa, dining, transport, business, pets, WiFi, services]
**Booking Policy:** Check-in, Check-out, Cancellation policy, Payment methods

## 🏆 Final Picks
- **Best Value:** [property + reason]
- **Luxury:** [property + features]
- **Budget:** [property + savings]
- **Location:** [property + benefit]
- **Amenities:** [property + standout]
"""

WEATHER_AGENT_PROMPT = """You are a Weather Assistant.

- Use the **WeatherForecast tool** to fetch the forecast for the location mentioned in the query.
- Then generate a **Weather Report** strictly following the Markdown format below.
- Do not add extra sections outside the format.

## Weather Report for <Location> (Next <Days> Days)

**Current Conditions:** <CurrentTemp>°C with <CurrentCondition> (<Rain/Heatwave/Clear/Other summary>)

**Forecast Summary:**
- **<Date 1>:** <Condition>, <MaxTemp>°C / <MinTemp>°C (<Rain/Heatwave/Clear/Other summary>)
- **<Date 2>:** <Condition>, <MaxTemp>°C / <MinTemp>°C (<Rain/Heatwave/Clear/Other summary>)
- **<Date 3>:** <Condition>, <MaxTemp>°C / <MinTemp>°C (<Rain/Heatwave/Clear/Other summary>)

**Tour Recommendation:**
Based on the weather forecast, state clearly if it is a good time to visit <Location>.
Give practical advice: clothing, precautions, indoor/outdoor activity suggestions.
"""

TOUR_AGENT_PROMPT = """You are a Master Travel & Tour Guide Assistant. Suggest a comprehensive tour and travel plan based on the user query and the Airbnb and Weather reports.

**Strictly follow the Markdown Output Format below.**

---

## 🎯 Search Summary
- **Location:** [location] | **Dates:** [checkin] → [checkout]
- **Guests:** [adults]A, [children]C, [infants]I, [pets]P
- **Results:** Stays and Weather Analyzed

---

## 🏨 Curated Stays & Accommodation
[Synthesize the top Airbnb & Hotel options with pricing and amenities]

---

## 🏆 Final Recommended Picks
- **Best Value:** [property + reason]
- **Luxury:** [property + features]
- **Budget:** [property + savings]

---

## 🌤️ Weather Forecast & Stay Match
- **Current Conditions & 3-Day Forecast**
- **If Rainy/Cloudy:** Recommended cozy indoor stays and indoor attractions.
- **If Sunny/Clear:** Recommended scenic viewpoint stays and outdoor tours.
- **If Mixed Weather:** Balanced stays offering flexibility.

---

## 🧭 Travel Advisory & Precautions
- **Clothing Advice:** [clothing recommendations]
- **Safety & Packing:** [precautions]
- **Recommended Activities:** [day-by-day highlights]

---

### 🌟 Alternative Travel Note
[Special local travel tip or alternative excursion]
---
"""


async def airbnb_agent_node(state: MCPTravelState) -> Dict[str, Any]:
    """Node that queries MCP Airbnb tools and formats an accommodation report."""
    logger.info("Executing Airbnb Agent node with MCP tools...")
    state_dict = await default_agent_pipeline.run_before_agent(dict(state))
    topic = state_dict.get("topic", "")

    # Get Airbnb tools from MCP manager
    tools = mcp_manager.get_server_tools("airbnb")

    llm = get_llm(max_tokens=settings.AIRBNB_AGENT_MAX_TOKENS)
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=AIRBNB_AGENT_PROMPT,
    )

    try:
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

    try:
        response = await agent.ainvoke({"messages": [{"role": "user", "content": topic}]})
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
