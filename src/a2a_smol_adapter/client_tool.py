"""SmolA2ADelegateTool — A smolagents Tool to delegate tasks to remote A2A agents."""

from __future__ import annotations

import logging
import time
import uuid

import httpx
from smolagents import Tool

logger = logging.getLogger(__name__)


class SmolA2ADelegateTool(Tool):
    """Delegates tasks to remote A2A-compliant agents via JSON-RPC."""

    name = "delegate_to_a2a"
    description = (
        "Delegate a task to a remote A2A-compliant agent. "
        "Sends the task text to the remote agent and returns its response."
    )
    inputs = {
        "url": {"type": "string", "description": "The A2A endpoint URL of the remote agent"},
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
        api_key: str | None = None,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
        **kwargs,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be a positive number")
        if max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        super().__init__(**kwargs)
        self._default_url = remote_url
        self._timeout = timeout
        self._api_key = api_key
        self._max_retries = max_retries
        self._http_client = http_client

    def forward(self, url: str, task: str) -> str:
        target_url = url or self._default_url
        if not target_url:
            return "Error: No remote URL provided and no default URL configured."
        if not task:
            return "Error: No task description provided."
        return self._send_task(target_url, task)

    def _send_task(self, base_url: str, task_text: str) -> str:
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
                }
            },
        }

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        attempts = 0
        max_attempts = 1 + self._max_retries

        while attempts < max_attempts:
            try:
                if self._http_client:
                    resp = self._http_client.post(rpc_url, json=payload, headers=headers)
                else:
                    with httpx.Client(timeout=self._timeout) as client:
                        resp = client.post(rpc_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return self._extract_result(data)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                attempts += 1
                if attempts >= max_attempts:
                    logger.error(
                        "Failed to send task to %s after %d attempts: %s",
                        rpc_url,
                        attempts,
                        exc,
                    )
                    return f"Error communicating with remote agent: {exc}"
                backoff = 2 ** (attempts - 1)  # 1s, 2s
                logger.warning(
                    "Retry %d/%d for %s after %ss: %s",
                    attempts,
                    self._max_retries,
                    rpc_url,
                    backoff,
                    exc,
                )
                time.sleep(backoff)
            except (httpx.HTTPStatusError, ValueError) as exc:
                logger.error("Failed to send task to %s: %s", rpc_url, exc)
                return f"Error communicating with remote agent: {exc}"

        return "Error: unexpected retry loop exit"

    def _extract_result(self, rpc_response: dict) -> str:
        if not rpc_response or not isinstance(rpc_response, dict):
            return "Error: Received invalid JSON-RPC response"
        if "error" in rpc_response:
            error = rpc_response["error"]
            return f"Remote agent error: {error.get('message', str(error))}"
        result = rpc_response.get("result", {})
        artifacts = result.get("artifacts", [])
        if artifacts:
            texts = [
                p["text"] for a in artifacts for p in a.get("parts", []) if p.get("kind") == "text"
            ]
            if texts:
                return "\n".join(texts)
        parts = result.get("parts", [])
        if parts:
            texts = [p["text"] for p in parts if p.get("kind") == "text"]
            if texts:
                return "\n".join(texts)
        return f"Remote agent returned: {result}"
