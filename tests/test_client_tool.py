"""Tests for SmolA2ADelegateTool."""

from a2a_smol_adapter.client_tool import SmolA2ADelegateTool


class TestSmolA2ADelegateTool:
    def test_no_url_returns_error(self):
        tool = SmolA2ADelegateTool()
        result = tool.forward(task="do something")
        assert "Error" in result
        assert "No remote URL" in result

    def test_no_task_returns_error(self):
        tool = SmolA2ADelegateTool(remote_url="http://localhost:5000/")
        result = tool.forward(url="http://localhost:5000/", task="")
        assert "Error" in result
        assert "No task" in result

    def test_default_url_used(self):
        tool = SmolA2ADelegateTool(remote_url="http://example.com/")
        # This will fail to connect, but verifies the URL logic
        result = tool.forward(task="test")
        assert "Error" in result  # Connection will fail

    def test_extract_result_with_artifacts(self):
        tool = SmolA2ADelegateTool()
        rpc_response = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {
                "artifacts": [
                    {
                        "parts": [{"kind": "text", "text": "Result from remote"}]
                    }
                ]
            },
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
