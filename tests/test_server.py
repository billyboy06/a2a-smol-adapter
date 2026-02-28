"""Tests for SmolA2AServer."""

from unittest.mock import MagicMock, patch

import pytest

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

    def test_empty_parts(self):
        msg = MagicMock()
        msg.parts = []
        assert _extract_text(msg) == ""

    def test_non_text_parts_skipped(self):
        msg = MagicMock()
        part = MagicMock(spec=[])  # no text attribute
        msg.parts = [part]
        assert _extract_text(msg) == ""


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
