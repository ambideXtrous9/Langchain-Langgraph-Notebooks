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
