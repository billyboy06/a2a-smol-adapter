# A2A-Smol-Adapter

[![CI](https://github.com/billyboy06/a2a-smol-adapter/actions/workflows/ci.yml/badge.svg)](https://github.com/billyboy06/a2a-smol-adapter/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/a2a-smol-adapter)](https://pypi.org/project/a2a-smol-adapter/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Bridge between [smolagents](https://github.com/huggingface/smolagents) (HuggingFace) and the [A2A protocol](https://github.com/google/A2A) (Google).

Expose any smolagents `CodeAgent` as an A2A-compliant server, or delegate tasks from a `CodeAgent` to remote A2A agents — in a few lines of Python.

## Why?

The **Agent2Agent (A2A)** protocol is an open standard for agent interoperability. **smolagents** is HuggingFace's lightweight agent framework. This library bridges both, enabling:

- Your smolagents agents to be discoverable and callable by any A2A-compatible client
- Your agents to delegate work to any remote A2A agent (LangChain, CrewAI, Google ADK, etc.)
- Multi-agent systems where agents from different frameworks collaborate seamlessly

## Features

| Feature | Description |
|---------|-------------|
| **A2A Server** | Wrap a `CodeAgent` in a FastAPI server that speaks JSON-RPC 2.0 |
| **A2A Client Tool** | `smolagents.Tool` to delegate work to any remote A2A agent |
| **Agent Card** | Auto-generated discovery endpoint at `/.well-known/agent-card.json` |
| **API Key Auth** | Optional Bearer token authentication on server and client |
| **SSE Streaming** | Intermediate progress events via `message/stream` |
| **Retry with Backoff** | Exponential backoff on transient network errors (client) |
| **Configurable Timeout** | Server-side agent execution timeout with proper failure events |
| **Health Endpoint** | `GET /health` for Kubernetes liveness/readiness probes |

## Installation

```bash
pip install a2a-smol-adapter
```

Or from source:

```bash
git clone https://github.com/billyboy06/a2a-smol-adapter.git
cd a2a-smol-adapter
pip install -e ".[dev]"
```

## Quick Start

### Expose an agent as A2A server

```python
import os
from smolagents import CodeAgent, InferenceClientModel
from a2a_smol_adapter import SmolA2AServer

agent = CodeAgent(tools=[], model=InferenceClientModel())

server = SmolA2AServer(
    agent,
    name="my-agent",
    host="0.0.0.0",             # listen on all interfaces (default: 127.0.0.1)
    port=5001,
    api_key=os.environ.get("A2A_API_KEY"),  # optional auth via env var
    agent_timeout=60.0,         # optional timeout (default: 120s)
)
server.run()
# Agent card → http://localhost:5001/.well-known/agent-card.json
# Health     → http://localhost:5001/health
```

### Delegate to a remote A2A agent

```python
import os
from smolagents import CodeAgent, InferenceClientModel
from a2a_smol_adapter import SmolA2ADelegateTool

delegate = SmolA2ADelegateTool(
    remote_url="http://remote-agent:5001/",
    api_key=os.environ.get("A2A_API_KEY"),  # optional, matches server auth
    max_retries=2,              # retry on network errors (default: 2)
)

agent = CodeAgent(tools=[delegate], model=InferenceClientModel())
result = agent.run("Ask the remote agent to compute pi to 50 digits")
```

## Architecture

```
┌──────────────────┐          ┌──────────────────────────────────────┐
│  Any A2A Client  │          │  SmolA2AServer                      │
│  (LangChain,     │  JSON-   │  ┌──────────┐  ┌────────────────┐  │
│   CrewAI,        │  RPC 2.0 │  │ FastAPI   │  │ SmolAgent      │  │
│   Google ADK,    │ ────────►│  │ + Auth    │─►│ Executor       │  │
│   curl...)       │          │  │ + Health  │  │ (async bridge) │  │
└──────────────────┘          │  └──────────┘  └───────┬────────┘  │
                              │                        │           │
                              │                ┌───────▼────────┐  │
                              │                │ smolagents     │  │
                              │                │ CodeAgent.run()│  │
                              │                └────────────────┘  │
                              └──────────────────────────────────────┘

┌──────────────────────────────────────┐          ┌──────────────────┐
│  Your smolagents CodeAgent           │          │  Any A2A Server  │
│  ┌────────────────────────────────┐  │  JSON-   │  (this lib,      │
│  │ SmolA2ADelegateTool            │  │  RPC 2.0 │   Google ADK,    │
│  │ (auto-retry, auth, timeout)   │──│─────────►│   LangChain...)  │
│  └────────────────────────────────┘  │          └──────────────────┘
└──────────────────────────────────────┘
```

## API Reference

### `SmolA2AServer`

```python
SmolA2AServer(
    agent: CodeAgent,
    *,
    name: str = "smol-agent",
    description: str = "...",
    version: str = "0.1.0",
    host: str = "127.0.0.1",
    port: int = 5000,
    skills: list[dict] | None = None,
    api_key: str | None = None,        # Bearer token auth
    agent_timeout: float = 120.0,      # seconds before timeout
)
```

| Method | Description |
|--------|-------------|
| `run()` | Start the uvicorn server |
| `build_app()` | Return the FastAPI app (for custom deployments, ASGI) |
| `agent_card` | The A2A `AgentCard` with name, skills, capabilities |

### `SmolA2ADelegateTool`

```python
SmolA2ADelegateTool(
    remote_url: str = "",
    timeout: float = 120.0,
    api_key: str | None = None,        # Bearer token for remote server
    max_retries: int = 2,              # retries on ConnectError/Timeout
    http_client: httpx.Client | None = None,  # injectable for testing
)
```

Usable as a standard `smolagents.Tool` — add it to your agent's tool list and call via `delegate_to_a2a(url, task)`.

## Testing

```bash
pip install -e ".[dev]"

# Run all 69 tests
pytest -v

# Lint
ruff check src/ tests/
```

Test coverage includes:
- Unit tests for server executor, client tool, auth middleware, healthcheck
- Integration tests with full cycle: discovery → send task → receive artifact
- Auth scenarios: valid key, invalid key, missing key, exempt paths
- Retry behavior: exponential backoff, exhausted retries, no retry on 4xx/5xx
- Timeout: agent execution timeout with proper failure events
- Streaming: intermediate working events from agent steps

## Project Structure

```
src/a2a_smol_adapter/
├── __init__.py         # Public API: SmolA2AServer, SmolA2ADelegateTool
├── server.py           # A2A server, executor, auth middleware, healthcheck
└── client_tool.py      # A2A client tool with retry, auth, DI

tests/
├── test_server.py      # 38 tests — executor, auth, streaming, health
├── test_client_tool.py # 23 tests — retry, auth header, DI, extraction
└── integration/
    └── test_end_to_end.py  # 8 tests — full cycle with ASGI transport

examples/
├── basic_server.py     # Minimal server setup
└── basic_client.py     # Minimal client delegation
```

## Security Considerations

- **API key comparison** uses `hmac.compare_digest` (timing-safe) to prevent side-channel attacks
- **Default host** is `127.0.0.1` (localhost only) — use `host="0.0.0.0"` explicitly for network-facing deployments
- **Prompt size** is capped at 100KB to prevent abuse
- **No rate limiting** built-in — use a reverse proxy (nginx, Traefik) for rate limiting in production
- **Security headers** (HSTS, CSP, etc.) are the responsibility of your reverse proxy
- **Prompt injection**: `CodeAgent` generates and executes Python code from user prompts. Use smolagents' sandboxing features (`LocalPythonExecutor` restrictions) when exposing to untrusted users
- **Consumer responsibility**: error messages from remote agents are returned as-is — escape them before rendering in HTML contexts
- **API keys** should be loaded from environment variables, never hardcoded (see examples)

## Built With

- [a2a-sdk](https://github.com/google/A2A/tree/main/sdk/python) — Official A2A Python SDK
- [smolagents](https://github.com/huggingface/smolagents) — HuggingFace agent framework
- [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) — HTTP server
- [httpx](https://www.python-httpx.org/) — HTTP client

## License

[MIT](LICENSE)
