"""Unit and Integration Tests for Model Context Protocol (MCP) and Travel Multi-Agent Graph."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from app.main import app
from app.core.mcp import MCPClientManager
from app.tools.weather import extract_weather, weather_forecast_tool
from app.graphs.mcp.builder import MCPTravelGraphBuilder, create_mcp_travel_graph


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient context with lifespan execution."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def auth_headers(client):
    """Creates a test user and returns Authorization Bearer headers."""
    email = "mcp_tester@test.com"
    pwd = "McpPassword123!"
    client.post(
        "/auth/signup",
        json={"email": email, "full_name": "MCP Tester", "password": pwd},
    )
    login_res = client.post(
        "/auth/login",
        data={"username": email, "password": pwd},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_extract_weather_formatting():
    """Tests formatting of WeatherAPI structured JSON."""
    mock_data = {
        "location": {"name": "Darjeeling", "region": "West Bengal", "country": "India"},
        "current": {
            "condition": {"text": "Sunny"},
            "temp_c": 18.5,
            "feelslike_c": 18.5,
            "humidity": 55,
            "gust_kph": 8.0,
            "pressure_mb": 1015,
        },
        "forecast": {
            "forecastday": [
                {
                    "date": "2026-08-25",
                    "day": {
                        "condition": {"text": "Clear"},
                        "maxtemp_c": 22.0,
                        "mintemp_c": 14.0,
                        "avghumidity": 50,
                        "maxwind_kph": 10.0,
                    },
                }
            ]
        },
    }
    result = extract_weather(mock_data)
    assert "Darjeeling" in result
    assert "18.5°C" in result
    assert "2026-08-25" in result
    assert "Clear" in result


def test_weather_forecast_tool_invocation():
    """Tests direct invocation of weather_forecast_tool."""
    res = weather_forecast_tool.invoke({"location": "Darjeeling", "days": 3})
    assert isinstance(res, str)
    assert len(res) > 20
    assert "Location" in res or "Temp" in res


@pytest.mark.asyncio
async def test_mcp_client_manager_lifecycle():
    """Tests MCPClientManager initialize, multi-server tool discovery (Airbnb + Pinecone), and shutdown."""
    manager = MCPClientManager()
    await manager.initialize()
    assert manager.is_initialized is True

    status = manager.get_server_status()
    assert "airbnb" in status or "pinecone" in status
    assert len(status) >= 1

    all_tools = manager.get_all_tools()
    assert len(all_tools) >= 1

    await manager.shutdown()
    assert manager.is_initialized is False


def test_mcp_hp_graph_structure():
    """Tests StateGraph assembly for Harry Potter QA mode."""
    builder = MCPTravelGraphBuilder()
    compiled = builder.build_hp_graph()
    assert compiled is not None

    mermaid = builder.get_mermaid_graph(mode="harry_potter")
    assert "hpSearchAgent" in mermaid
    assert "hpLoreScholar" in mermaid


def test_mcp_airbnb_graph_structure():
    """Tests StateGraph assembly for Airbnb travel mode."""
    builder = MCPTravelGraphBuilder()
    compiled = builder.build_airbnb_graph()
    assert compiled is not None

    mermaid = builder.get_mermaid_graph(mode="airbnb")
    assert "airbnbAgent" in mermaid
    assert "weatherAgent" in mermaid
    assert "tourAgent" in mermaid


@pytest.mark.asyncio
async def test_mcp_hp_qa_execution():
    """Tests Harry Potter QA state graph execution with mocked LLM and MCP responses."""
    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(
        return_value=AIMessage(content="# ⚡ The History of the Elder Wand\nCanonical lore and allegiance rules.")
    )
    mock_llm_instance.with_config.return_value = mock_llm_instance

    mock_agent_instance = MagicMock()
    mock_agent_instance.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="Retrieved book passages from hpvdb-openai on the Elder Wand.")]}
    )

    with patch("app.graphs.mcp.nodes.get_llm", return_value=mock_llm_instance), \
         patch("app.graphs.mcp.nodes.create_react_agent", return_value=mock_agent_instance):

        graph = create_mcp_travel_graph(mode="harry_potter")
        initial_state = {
            "topic": "Explain the history of the Elder Wand",
            "mode": "harry_potter",
            "knowledge": [],
            "airbnb_report": "",
            "weather_report": "",
            "hp_report": "",
            "summary": "",
        }

        result = await graph.ainvoke(initial_state)

        assert result is not None
        assert "hp_report" in result
        assert "summary" in result
        assert "Elder Wand" in result["summary"]


@pytest.mark.asyncio
async def test_mcp_airbnb_execution():
    """Tests Airbnb travel state graph execution with mocked LLM responses."""
    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(
        return_value=AIMessage(content="## 🎯 Final Travel & Stay Guide\nTop Airbnbs matched with ideal forecast.")
    )
    mock_llm_instance.with_config.return_value = mock_llm_instance

    mock_agent_instance = MagicMock()
    mock_agent_instance.ainvoke = AsyncMock(
        return_value={"messages": [AIMessage(content="Curated Airbnb stay report with listings.")]}
    )

    with patch("app.graphs.mcp.nodes.get_llm", return_value=mock_llm_instance), \
         patch("app.graphs.mcp.nodes.create_react_agent", return_value=mock_agent_instance):

        graph = create_mcp_travel_graph(mode="airbnb")
        initial_state = {
            "topic": "Find me the top 3 cottages in Darjeeling for 2 people",
            "mode": "airbnb",
            "knowledge": [],
            "airbnb_report": "",
            "weather_report": "",
            "hp_report": "",
            "summary": "",
        }

        result = await graph.ainvoke(initial_state)

        assert result is not None
        assert "airbnb_report" in result
        assert "weather_report" in result
        assert "summary" in result
        assert "Final Travel & Stay Guide" in result["summary"]


def test_mcp_tools_endpoint_authenticated(client, auth_headers):
    """Tests GET /mcp/tools endpoint with valid authentication."""
    response = client.get("/mcp/tools", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "servers" in data
    assert "airbnb" in data["servers"]
    assert data["total_tools"] >= 1


def test_mcp_tools_endpoint_unauthenticated(client):
    """Tests GET /mcp/tools returns 401 when unauthenticated."""
    response = client.get("/mcp/tools")
    assert response.status_code == 401


def test_mcp_travel_mermaid_endpoint(client):
    """Tests GET /mcp/mermaid and /mcp/travel/mermaid endpoints with mode query parameters."""
    response_hp = client.get("/mcp/mermaid?mode=harry_potter")
    assert response_hp.status_code == 200
    assert "hpSearchAgent" in response_hp.text
    assert "hpLoreScholar" in response_hp.text

    response_airbnb = client.get("/mcp/travel/mermaid?mode=airbnb")
    assert response_airbnb.status_code == 200
    assert "airbnbAgent" in response_airbnb.text
    assert "tourAgent" in response_airbnb.text


def test_mcp_travel_run_endpoint(client, auth_headers):
    """Tests POST /mcp/run and /mcp/travel/run endpoint with mock execution."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "hp_report": "Retrieved passages from hpvdb-openai.",
            "airbnb_report": "",
            "weather_report": "",
            "summary": "# Canonical Lore Answer\nElder Wand wandlore breakdown.",
        }
    )

    with patch("app.api.v1.endpoints.mcp.create_hp_graph", return_value=mock_graph):
        response = client.post(
            "/mcp/run",
            json={"topic": "Elder wand lore", "mode": "harry_potter"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "Elder wand lore"
        assert data["mode"] == "harry_potter"
        assert "final_plan" in data
        assert "Elder Wand" in data["final_plan"]


def test_mcp_travel_stream_endpoint(client, auth_headers):
    """Tests POST /mcp/stream and /mcp/travel/stream SSE streaming endpoint."""
    mock_graph = MagicMock()

    async def mock_astream_events(state, version):
        yield {
            "event": "on_chat_model_start",
            "metadata": {"langgraph_node": "hpSearchAgent"},
            "tags": [],
        }
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_node": "hpLoreScholar"},
            "tags": ["HPLoreScholar"],
            "data": {"chunk": AIMessage(content="The Elder Wand is one of three Deathly Hallows.")},
        }

    mock_graph.astream_events = mock_astream_events

    with patch("app.api.v1.endpoints.mcp.create_hp_graph", return_value=mock_graph):
        response = client.post(
            "/mcp/stream",
            json={"topic": "Elder wand history", "mode": "harry_potter"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "hpSearchAgent" in body
        assert "The Elder Wand is one of three Deathly Hallows." in body
