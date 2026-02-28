"""Tests for SmolA2ADelegateTool."""

from __future__ import annotations

import httpx
import pytest

from a2a_smol_adapter.client_tool import SmolA2ADelegateTool

SEND_TASK_RESPONSE = {
    "jsonrpc": "2.0",
    "id": "abc",
    "result": {
        "artifacts": [{"parts": [{"kind": "text", "text": "Remote result"}]}],
    },
}


class TestSmolA2ADelegateTool:
    def test_no_url_returns_error(self):
        tool = SmolA2ADelegateTool()
        result = tool.forward(url="", task="do something")
        assert "Error" in result
        assert "No remote URL" in result

    def test_no_task_returns_error(self):
        tool = SmolA2ADelegateTool(remote_url="http://localhost:5000/")
        result = tool.forward(url="http://localhost:5000/", task="")
        assert "Error" in result
        assert "No task" in result

    def test_default_url_used(self, httpx_mock):
        """Default URL is used when url arg is empty."""
        httpx_mock.add_response(
            url="http://example.com/",
            json=SEND_TASK_RESPONSE,
        )
        tool = SmolA2ADelegateTool(remote_url="http://example.com/")
        result = tool.forward(url="", task="test")
        assert result == "Remote result"

    def test_invalid_timeout_raises(self):
        with pytest.raises(ValueError, match="timeout must be a positive number"):
            SmolA2ADelegateTool(timeout=0)

    def test_negative_timeout_raises(self):
        with pytest.raises(ValueError, match="timeout must be a positive number"):
            SmolA2ADelegateTool(timeout=-5)

    def test_extract_result_with_artifacts(self):
        tool = SmolA2ADelegateTool()
        rpc_response = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {"artifacts": [{"parts": [{"kind": "text", "text": "Result from remote"}]}]},
        }
        assert tool._extract_result(rpc_response) == "Result from remote"

    def test_extract_result_with_error(self):
        tool = SmolA2ADelegateTool()
        rpc_response = {
            "jsonrpc": "2.0",
            "id": "123",
            "error": {"code": -32000, "message": "Agent failed"},
        }
        result = tool._extract_result(rpc_response)
        assert "error" in result.lower()
        assert "Agent failed" in result

    def test_extract_result_with_message_parts(self):
        tool = SmolA2ADelegateTool()
        rpc_response = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {"parts": [{"kind": "text", "text": "Direct message response"}]},
        }
        assert tool._extract_result(rpc_response) == "Direct message response"

    def test_extract_result_with_empty_result(self):
        tool = SmolA2ADelegateTool()
        rpc_response = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {},
        }
        result = tool._extract_result(rpc_response)
        assert "Remote agent returned" in result

    def test_extract_result_with_none(self):
        tool = SmolA2ADelegateTool()
        assert "invalid JSON-RPC" in tool._extract_result(None)

    def test_extract_result_with_non_dict(self):
        tool = SmolA2ADelegateTool()
        assert "invalid JSON-RPC" in tool._extract_result("not a dict")


class TestSendTask:
    def test_success_with_artifact(self, httpx_mock):
        httpx_mock.add_response(
            url="http://remote:5000/",
            json=SEND_TASK_RESPONSE,
        )
        tool = SmolA2ADelegateTool()
        result = tool._send_task("http://remote:5000/", "do something")
        assert result == "Remote result"

    def test_http_500_returns_error(self, httpx_mock):
        httpx_mock.add_response(
            url="http://remote:5000/",
            status_code=500,
        )
        tool = SmolA2ADelegateTool()
        result = tool._send_task("http://remote:5000/", "do something")
        assert "Error communicating" in result

    def test_connect_error_returns_error(self, httpx_mock):
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url="http://remote:5000/",
        )
        tool = SmolA2ADelegateTool()
        result = tool._send_task("http://remote:5000/", "do something")
        assert "Error communicating" in result
