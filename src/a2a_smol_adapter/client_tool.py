"""SmolA2ADelegateTool — A smolagents Tool to delegate tasks to remote A2A agents."""

from __future__ import annotations

import logging
import uuid

import httpx
from smolagents import Tool

logger = logging.getLogger(__name__)


class SmolA2ADelegateTool(Tool):
    """A smolagents Tool that delegates tasks to a remote A2A-compliant agent.

    When a CodeAgent uses this tool, it forges a JSON-RPC 2.0 request,
    sends it to the remote agent's A2A endpoint, and returns the result.

    Usage:
        delegate = SmolA2ADelegateTool(
            remote_url="http://remote-agent:5000/",
        )
        agent = CodeAgent(tools=[delegate], model=model)
        agent.run("Ask the math agent to compute pi to 100 digits")
    """

    name = "delegate_to_a2a"
    description = (
        "Delegate a task to a remote A2A-compliant agent. "
        "Sends the task text to the remote agent and returns its response. "
        "Use this when the current agent cannot handle the task alone."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The A2A endpoint URL of the remote agent (e.g. http://host:port/)",
        },
        "task": {
            "type": "string",
            "description": "The task description to send to the remote agent",
        },
    }
    output_type = "string"

    def __init__(
        self,
        remote_url: str = "",
        timeout: float = 120.0,
        **kwargs,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be a positive number")
        super().__init__(**kwargs)
        self._default_url = remote_url
        self._timeout = timeout

    def forward(self, url: str, task: str) -> str:
        """Send a task to a remote A2A agent and return the result.

        Args:
            url: The A2A endpoint URL of the remote agent.
            task: The task description to send to the remote agent.

        Returns:
            The text result from the remote agent, or an error message.
        """
        target_url = url or self._default_url
        if not target_url:
            return "Error: No remote URL provided and no default URL configured."

        if not task:
            return "Error: No task description provided."

        return self._send_task(target_url, task)

    def _send_task(self, base_url: str, task_text: str) -> str:
        """Send a message/send JSON-RPC request to the remote agent."""
        rpc_url = base_url.rstrip("/") + "/"
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": task_text}],
                },
            },
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(rpc_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Failed to send task to %s: %s", rpc_url, exc)
            return f"Error communicating with remote agent: {exc}"

        return self._extract_result(data)

    def _extract_result(self, rpc_response: dict) -> str:
        """Extract text from a JSON-RPC response."""
        if not rpc_response or not isinstance(rpc_response, dict):
            return "Error: Received invalid JSON-RPC response"

        if "error" in rpc_response:
            error = rpc_response["error"]
            return f"Remote agent error: {error.get('message', str(error))}"

        result = rpc_response.get("result", {})

        # Result can be a Task or a Message
        # Try to extract artifacts from a Task
        artifacts = result.get("artifacts", [])
        if artifacts:
            texts = []
            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("kind") == "text":
                        texts.append(part["text"])
            if texts:
                return "\n".join(texts)

        # Try to extract from message parts
        parts = result.get("parts", [])
        if parts:
            texts = [p["text"] for p in parts if p.get("kind") == "text"]
            if texts:
                return "\n".join(texts)

        return f"Remote agent returned: {result}"
