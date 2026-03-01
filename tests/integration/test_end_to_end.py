"""End-to-end integration tests: discovery -> send task -> receive artifact."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from starlette.testclient import TestClient

from a2a_smol_adapter.client_tool import SmolA2ADelegateTool
from a2a_smol_adapter.server import SmolA2AServer


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.run.return_value = "42"
    return agent


@pytest.fixture
def server(mock_agent):
    return SmolA2AServer(mock_agent, name="test-e2e", version="0.2.0", port=9999)


@pytest.fixture
def server_with_auth(mock_agent):
    return SmolA2AServer(
        mock_agent, name="test-e2e-auth", version="0.2.0", port=9999, api_key="e2e-secret"
    )


@pytest.fixture
def test_client(server):
    return TestClient(server.build_app())


@pytest.fixture
def test_client_with_auth(server_with_auth):
    return TestClient(server_with_auth.build_app())


@pytest.fixture
def http_client(server):
    """httpx.Client backed by starlette TestClient transport for DI into SmolA2ADelegateTool."""
    app = server.build_app()
    transport = httpx.MockTransport(TestClient(app).transport.handle_request)
    return httpx.Client(transport=transport, base_url="http://testserver")


@pytest.fixture
def http_client_with_auth(server_with_auth):
    app = server_with_auth.build_app()
    transport = httpx.MockTransport(TestClient(app).transport.handle_request)
    return httpx.Client(transport=transport, base_url="http://testserver")


class TestDiscovery:
    def test_agent_card_discovery(self, test_client):
        resp = test_client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "test-e2e"
        assert card["version"] == "0.2.0"
        assert "skills" in card

    def test_agent_card_with_auth_is_public(self, test_client_with_auth):
        resp = test_client_with_auth.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-e2e-auth"


class TestFullCycle:
    def test_send_task_and_receive_artifact(self, test_client, mock_agent):
        """Full cycle: send task via JSON-RPC -> receive artifact with result."""
        mock_agent.run.return_value = "The answer is 42"

        tool = SmolA2ADelegateTool(http_client=test_client)
        result = tool._send_task("http://testserver", "What is 6 * 7?")

        assert "The answer is 42" in result
        mock_agent.run.assert_called_once()

    def test_send_task_with_auth(self, test_client_with_auth, mock_agent):
        """Full cycle with authentication."""
        mock_agent.run.return_value = "Authenticated result"

        tool = SmolA2ADelegateTool(http_client=test_client_with_auth, api_key="e2e-secret")
        result = tool._send_task("http://testserver", "Authenticated task")

        assert "Authenticated result" in result

    def test_send_task_without_auth_fails(self, test_client_with_auth):
        """Sending without auth key to protected server returns 401 error."""
        tool = SmolA2ADelegateTool(http_client=test_client_with_auth)
        result = tool._send_task("http://testserver", "Unauthorized task")

        assert "Error communicating" in result

    def test_send_task_with_wrong_auth_fails(self, test_client_with_auth):
        """Wrong auth key returns 401."""
        tool = SmolA2ADelegateTool(http_client=test_client_with_auth, api_key="wrong-key")
        result = tool._send_task("http://testserver", "Bad auth task")

        assert "Error communicating" in result


class TestHealthEndToEnd:
    def test_health_endpoint(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["agent"] == "test-e2e"

    def test_health_with_auth_no_key_needed(self, test_client_with_auth):
        resp = test_client_with_auth.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
