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

    def test_streaming_is_false(self):
        server = SmolA2AServer(MagicMock())
        assert server.agent_card.capabilities.streaming is False


class TestSmolAgentExecutor:
    def test_none_agent_raises(self):
        with pytest.raises(ValueError, match="agent is required"):
            SmolAgentExecutor(None)

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
        """When agent.run() raises, emit working -> failed(final=True) with message."""
        mock_agent.run.side_effect = RuntimeError("LLM exploded")
        executor = SmolAgentExecutor(mock_agent)

        await executor.execute(mock_context, mock_event_queue)

        calls = mock_event_queue.enqueue_event.call_args_list
        assert len(calls) == 2

        # First event: working
        assert calls[0].args[0].status.state == TaskState.working

        # Second event: failed
        event_failed = calls[1].args[0]
        assert event_failed.status.state == TaskState.failed
        assert event_failed.final is True

    async def test_execute_missing_task_raises(self, mock_agent, mock_event_queue):
        ctx = MagicMock()
        ctx.current_task = None
        ctx.message = MagicMock()
        executor = SmolAgentExecutor(mock_agent)
        with pytest.raises(ValueError, match="current_task"):
            await executor.execute(ctx, mock_event_queue)

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
