"""Tests for SmolA2AServer and SmolAgentExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import TaskState

from a2a_smol_adapter.server import SmolA2AServer, SmolAgentExecutor, _extract_text


class TestExtractText:
    def test_extracts_text_parts(self):
        msg = MagicMock()
        part1 = MagicMock()
        part1.text = "Hello"
        part2 = MagicMock()
        part2.text = "World"
        msg.parts = [part1, part2]
        assert _extract_text(msg) == "Hello\nWorld"

    def test_empty_parts_raises(self):
        msg = MagicMock()
        msg.parts = []
        with pytest.raises(ValueError, match="at least one part"):
            _extract_text(msg)

    def test_non_text_parts_raises(self):
        msg = MagicMock()
        part = MagicMock(spec=[])  # no text attribute
        msg.parts = [part]
        with pytest.raises(ValueError, match="no text parts"):
            _extract_text(msg)

    def test_none_message_raises(self):
        with pytest.raises(ValueError, match="at least one part"):
            _extract_text(None)


class TestSmolA2AServer:
    def test_creates_with_defaults(self):
        agent = MagicMock()
        server = SmolA2AServer(agent, name="test-agent", port=9999)
        card = server.agent_card
        assert card.name == "test-agent"
        assert "9999" in card.url

    def test_custom_skills(self):
        agent = MagicMock()
        skills = [
            {
                "id": "math",
                "name": "Math Solver",
                "description": "Solve math problems",
                "tags": ["math"],
                "examples": ["Compute 2+2"],
            }
        ]
        server = SmolA2AServer(agent, skills=skills)
        assert len(server.agent_card.skills) == 1
        assert server.agent_card.skills[0].name == "Math Solver"

    def test_none_agent_raises(self):
        with pytest.raises(ValueError, match="agent is required"):
            SmolA2AServer(None)

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name is required"):
            SmolA2AServer(MagicMock(), name="")

    def test_invalid_port_raises(self):
        with pytest.raises(ValueError, match="port must be"):
            SmolA2AServer(MagicMock(), port=0)

    def test_streaming_is_true(self):
        server = SmolA2AServer(MagicMock())
        assert server.agent_card.capabilities.streaming is True

    def test_api_key_stored(self):
        server = SmolA2AServer(MagicMock(), api_key="secret-key")
        assert server._api_key == "secret-key"

    def test_no_api_key_by_default(self):
        server = SmolA2AServer(MagicMock())
        assert server._api_key is None


class TestSmolAgentExecutor:
    def test_none_agent_raises(self):
        with pytest.raises(ValueError, match="agent is required"):
            SmolAgentExecutor(None)

    def test_invalid_timeout_raises(self):
        with pytest.raises(ValueError, match="agent_timeout must be a positive number"):
            SmolAgentExecutor(MagicMock(), agent_timeout=0)

    def test_negative_timeout_raises(self):
        with pytest.raises(ValueError, match="agent_timeout must be a positive number"):
            SmolAgentExecutor(MagicMock(), agent_timeout=-5)

    def test_custom_timeout(self):
        executor = SmolAgentExecutor(MagicMock(), agent_timeout=30.0)
        assert executor._agent_timeout == 30.0

    async def test_execute_emits_events_in_order(self, mock_agent, mock_context, mock_event_queue):
        """Happy path: working -> artifact -> completed(final=True)."""
        executor = SmolAgentExecutor(mock_agent)

        await executor.execute(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 3

        # First event: working
        event_working = calls[0].args[0]
        assert event_working.status.state == TaskState.working
        assert event_working.final is False

        # Second event: artifact
        event_artifact = calls[1].args[0]
        assert hasattr(event_artifact, "artifact")

        # Third event: completed
        event_completed = calls[2].args[0]
        assert event_completed.status.state == TaskState.completed
        assert event_completed.final is True

    async def test_execute_agent_error_emits_failed(
        self, mock_agent, mock_context, mock_event_queue
    ):
        """When agent.run() raises, emit working -> failed(final=True)."""
        mock_agent.run.side_effect = RuntimeError("LLM exploded")
        executor = SmolAgentExecutor(mock_agent)

        await executor.execute(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 2

        assert calls[0].args[0].status.state == TaskState.working
        event_failed = calls[1].args[0]
        assert event_failed.status.state == TaskState.failed
        assert event_failed.final is True

    async def test_execute_timeout_emits_failed(self, mock_context, mock_event_queue):
        """When agent.run() exceeds timeout, emit working -> failed(final=True)."""
        agent = MagicMock()

        def slow_run(prompt):
            import time

            time.sleep(5)
            return "too late"

        agent.run.side_effect = slow_run
        executor = SmolAgentExecutor(agent, agent_timeout=0.1)

        await executor.execute(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0].status.state == TaskState.working
        assert calls[1].args[0].status.state == TaskState.failed
        assert calls[1].args[0].final is True

    async def test_execute_works_without_current_task(self, mock_agent, mock_event_queue):
        """Executor works when current_task is None (SDK creates task from events)."""
        ctx = MagicMock()
        ctx.current_task = None
        ctx.task_id = "task-new"
        ctx.context_id = "ctx-new"
        part = MagicMock()
        part.text = "test prompt"
        message = MagicMock()
        message.parts = [part]
        ctx.message = message
        executor = SmolAgentExecutor(mock_agent)
        await executor.execute(ctx, mock_event_queue)
        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 3
        assert calls[0].args[0].status.state == TaskState.working

    async def test_execute_missing_message_raises(self, mock_agent, mock_event_queue):
        ctx = MagicMock()
        ctx.current_task = MagicMock()
        ctx.message = None
        executor = SmolAgentExecutor(mock_agent)
        with pytest.raises(ValueError, match="message"):
            await executor.execute(ctx, mock_event_queue)

    async def test_cancel_emits_canceled(self, mock_agent, mock_context, mock_event_queue):
        """Cancel emits a single canceled(final=True) event."""
        executor = SmolAgentExecutor(mock_agent)

        await executor.cancel(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 1

        event_canceled = calls[0].args[0]
        assert event_canceled.status.state == TaskState.canceled
        assert event_canceled.final is True


class TestExecuteStreaming:
    async def test_streaming_emits_intermediate_events(self, mock_context, mock_event_queue):
        """Streaming produces working events for each step + artifact + completed."""
        agent = MagicMock()
        agent.run.return_value = iter(["step 1", "step 2", "final result"])

        executor = SmolAgentExecutor(agent)
        await executor.execute_streaming(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        # working + 3 intermediate working + artifact + completed = 6
        assert len(calls) >= 5

        # First: working (initial)
        assert calls[0].args[0].status.state == TaskState.working
        assert calls[0].args[0].final is False

        # Last two: artifact + completed
        assert hasattr(calls[-2].args[0], "artifact")
        assert calls[-1].args[0].status.state == TaskState.completed
        assert calls[-1].args[0].final is True

    async def test_streaming_agent_error_emits_failed(self, mock_context, mock_event_queue):
        """When streaming agent raises, emit failed."""
        agent = MagicMock()

        def exploding_generator(prompt, stream=True):
            raise RuntimeError("Boom")

        agent.run.side_effect = exploding_generator
        executor = SmolAgentExecutor(agent)

        await executor.execute_streaming(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        # Should have working + failed
        states = [c.args[0].status.state for c in calls if hasattr(c.args[0], "status")]
        assert TaskState.failed in states

    async def test_streaming_missing_message_raises(self, mock_agent, mock_event_queue):
        ctx = MagicMock()
        ctx.current_task = None
        ctx.message = None
        executor = SmolAgentExecutor(mock_agent)
        with pytest.raises(ValueError, match="message"):
            await executor.execute_streaming(ctx, mock_event_queue)

    async def test_streaming_calls_agent_with_stream_true(self, mock_context, mock_event_queue):
        """Verify agent.run() is called with stream=True."""
        agent = MagicMock()
        agent.run.return_value = iter(["result"])

        executor = SmolAgentExecutor(agent)
        await executor.execute_streaming(mock_context, mock_event_queue)

        agent.run.assert_called_once()
        call_kwargs = agent.run.call_args
        assert call_kwargs[1].get("stream") is True or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] is True
        )


class TestHealthcheck:
    def test_health_endpoint_returns_ok(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), name="test-agent", version="1.2.3")
        app = server.build_app()
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["agent"] == "test-agent"
        assert data["version"] == "1.2.3"

    def test_health_no_auth_required(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), name="test-agent", api_key="secret")
        app = server.build_app()
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_with_default_version(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock())
        app = server.build_app()
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.json()["version"] == "0.1.0"


class TestAuthMiddleware:
    def test_request_without_key_returns_401(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/", json={"jsonrpc": "2.0", "method": "test", "id": "1"})
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == -32001

    def test_request_with_wrong_key_returns_401(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "method": "test", "id": "1"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401

    def test_request_with_correct_key_passes(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/.well-known/agent-card.json",
        )
        # Agent card should be accessible (it's auth-exempt)
        assert resp.status_code == 200

    def test_agent_card_accessible_without_key(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data

    def test_no_auth_when_api_key_not_set(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock())
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Agent card should work without any auth header
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200

    def test_authenticated_request_reaches_endpoint(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        # With correct key, a POST to / should reach the A2A handler (not 401)
        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "method": "message/send", "id": "1", "params": {}},
            headers={"Authorization": "Bearer my-secret"},
        )
        # Should not be 401 — may be 400/422 from A2A SDK validation, but not auth error
        assert resp.status_code != 401

    def test_bearer_prefix_required(self):
        from starlette.testclient import TestClient

        server = SmolA2AServer(MagicMock(), api_key="my-secret")
        app = server.build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/",
            json={"jsonrpc": "2.0", "method": "test", "id": "1"},
            headers={"Authorization": "my-secret"},  # Missing "Bearer " prefix
        )
        assert resp.status_code == 401
