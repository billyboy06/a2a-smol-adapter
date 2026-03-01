"""Tests for SmolA2ADelegateTool."""

from __future__ import annotations

from unittest.mock import patch

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

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError, match="max_retries must be a non-negative integer"):
            SmolA2ADelegateTool(max_retries=-1)

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
        tool = SmolA2ADelegateTool(max_retries=0)
        result = tool._send_task("http://remote:5000/", "do something")
        assert "Error communicating" in result


class TestAuthHeader:
    def test_api_key_sends_bearer_header(self, httpx_mock):
        httpx_mock.add_response(url="http://remote:5000/", json=SEND_TASK_RESPONSE)
        tool = SmolA2ADelegateTool(api_key="test-key")
        tool._send_task("http://remote:5000/", "do something")

        request = httpx_mock.get_request()
        assert request.headers["authorization"] == "Bearer test-key"

    def test_no_api_key_no_auth_header(self, httpx_mock):
        httpx_mock.add_response(url="http://remote:5000/", json=SEND_TASK_RESPONSE)
        tool = SmolA2ADelegateTool()
        tool._send_task("http://remote:5000/", "do something")

        request = httpx_mock.get_request()
        assert "authorization" not in request.headers


class TestRetry:
    @patch("a2a_smol_adapter.client_tool.time.sleep")
    def test_retries_on_connect_error_then_succeeds(self, mock_sleep, httpx_mock):
        """Two ConnectErrors followed by success."""
        httpx_mock.add_exception(httpx.ConnectError("fail 1"), url="http://remote:5000/")
        httpx_mock.add_exception(httpx.ConnectError("fail 2"), url="http://remote:5000/")
        httpx_mock.add_response(url="http://remote:5000/", json=SEND_TASK_RESPONSE)

        tool = SmolA2ADelegateTool(max_retries=2)
        result = tool._send_task("http://remote:5000/", "task")
        assert result == "Remote result"
        assert mock_sleep.call_count == 2

    @patch("a2a_smol_adapter.client_tool.time.sleep")
    def test_retries_on_timeout_then_succeeds(self, mock_sleep, httpx_mock):
        """TimeoutException followed by success."""
        httpx_mock.add_exception(httpx.TimeoutException("timeout"), url="http://remote:5000/")
        httpx_mock.add_response(url="http://remote:5000/", json=SEND_TASK_RESPONSE)

        tool = SmolA2ADelegateTool(max_retries=1)
        result = tool._send_task("http://remote:5000/", "task")
        assert result == "Remote result"

    @patch("a2a_smol_adapter.client_tool.time.sleep")
    def test_exhausted_retries_returns_error(self, mock_sleep, httpx_mock):
        """All retries exhausted returns error."""
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")

        tool = SmolA2ADelegateTool(max_retries=2)
        result = tool._send_task("http://remote:5000/", "task")
        assert "Error communicating" in result

    def test_no_retry_on_http_4xx(self, httpx_mock):
        """HTTP 400 is not retried."""
        httpx_mock.add_response(url="http://remote:5000/", status_code=400)
        tool = SmolA2ADelegateTool(max_retries=2)
        result = tool._send_task("http://remote:5000/", "task")
        assert "Error communicating" in result

    def test_no_retry_on_http_5xx(self, httpx_mock):
        """HTTP 500 is not retried (application error)."""
        httpx_mock.add_response(url="http://remote:5000/", status_code=500)
        tool = SmolA2ADelegateTool(max_retries=2)
        result = tool._send_task("http://remote:5000/", "task")
        assert "Error communicating" in result

    @patch("a2a_smol_adapter.client_tool.time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep, httpx_mock):
        """Backoff is 1s then 2s."""
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")

        tool = SmolA2ADelegateTool(max_retries=2)
        tool._send_task("http://remote:5000/", "task")

        assert mock_sleep.call_args_list[0].args[0] == 1  # 2^0
        assert mock_sleep.call_args_list[1].args[0] == 2  # 2^1

    def test_zero_retries_no_retry(self, httpx_mock):
        """max_retries=0 means no retry at all."""
        httpx_mock.add_exception(httpx.ConnectError("fail"), url="http://remote:5000/")
        tool = SmolA2ADelegateTool(max_retries=0)
        result = tool._send_task("http://remote:5000/", "task")
        assert "Error communicating" in result


class TestHttpClientDI:
    def test_injected_client_is_used(self):
        """When http_client is provided, it's used instead of creating a new one."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = SEND_TASK_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        tool = SmolA2ADelegateTool(http_client=mock_client)
        result = tool._send_task("http://remote:5000/", "task")

        assert result == "Remote result"
        mock_client.post.assert_called_once()
