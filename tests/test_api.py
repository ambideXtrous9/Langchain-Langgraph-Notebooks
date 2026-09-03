"""Integration Tests for FastAPI Endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient context with lifespan execution."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Tests /health status endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_graph_mermaid_endpoint(client):
    """Tests /graph/mermaid endpoint returning graph diagram."""
    response = client.get("/graph/mermaid")
    assert response.status_code == 200
    assert len(response.text) > 0


@pytest.fixture(scope="module")
def auth_headers(client):
    """Creates a test user and returns Authorization Bearer headers."""
    email = "api_tester@test.com"
    pwd = "TesterPassword123!"
    client.post(
        "/auth/signup",
        json={"email": email, "full_name": "API Tester", "password": pwd},
    )
    login_res = client.post(
        "/auth/login",
        data={"username": email, "password": pwd},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_interact_empty_input(client, auth_headers):
    """Tests /interact endpoint validation on empty input with auth token."""
    response = client.post("/interact", json={}, headers=auth_headers)
    assert response.status_code == 200
    assert "No input provided" in response.text


def test_interaction_request_device_data_aliases():
    """Tests Pydantic alias resolution for normalized and legacy device keys."""
    from app.schemas.interact import InteractionRequest

    # Test legacy typo key
    req1 = InteractionRequest.model_validate({"userProvidedDeiveceData": "Cardio Stent"})
    assert req1.device_data == "Cardio Stent"
    assert req1.userProvidedDeiveceData == "Cardio Stent"

    # Test normalized snake_case key
    req2 = InteractionRequest.model_validate({"user_provided_device_data": "Neuro Stimulator"})
    assert req2.device_data == "Neuro Stimulator"
    assert req2.userProvidedDeiveceData == "Neuro Stimulator"

    # Test normalized camelCase key
    req3 = InteractionRequest.model_validate({"userProvidedDeviceData": "Infusion Pump"})
    assert req3.device_data == "Infusion Pump"


def test_websocket_auth_required(client):
    """Tests that connecting to /ws/interact without a valid JWT is rejected."""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/interact"):
            pass


def test_websocket_authenticated_connection(client, auth_headers):
    """Tests successful authenticated WebSocket handshake and thread initiation."""
    token = auth_headers["Authorization"].split(" ")[1]
    with client.websocket_connect(f"/ws/interact?token={token}") as ws:
        ws.send_json({"action": "start", "user_input": "Policy test inquiry"})
        first_msg = ws.receive_json()
        assert first_msg.get("type") == "thread_id"
        assert "thread_id" in first_msg


def test_sql_agent_caching():
    """Tests that load_sql_agent caches compiled agents across calls."""
    from app.agents.sql_agent import _agent_cache, load_sql_agent

    agent1 = load_sql_agent()
    agent2 = load_sql_agent()
    assert agent1 is agent2
    assert len(_agent_cache) >= 1
