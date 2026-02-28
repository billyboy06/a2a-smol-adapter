"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from smolagents import CodeAgent


@pytest.fixture
def mock_agent():
    """A mocked smolagents CodeAgent whose run() returns 'result'."""
    agent = MagicMock(spec=CodeAgent)
    agent.run.return_value = "result"
    return agent


@pytest.fixture
def mock_task():
    """A mocked A2A task with id and context_id."""
    task = MagicMock()
    task.id = "task-123"
    task.context_id = "ctx-456"
    return task


@pytest.fixture
def mock_context(mock_task):
    """A mocked RequestContext with a current_task and a single text message."""
    ctx = MagicMock(spec=RequestContext)
    ctx.current_task = mock_task

    part = MagicMock()
    part.text = "Hello agent"
    message = MagicMock()
    message.parts = [part]
    ctx.message = message
    return ctx


@pytest.fixture
def mock_event_queue():
    """An async-compatible mocked EventQueue."""
    queue = AsyncMock(spec=EventQueue)
    return queue
