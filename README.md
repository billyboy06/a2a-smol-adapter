# A2A-Smol-Adapter

Bridge between [smolagents](https://github.com/huggingface/smolagents) and the [A2A (Agent2Agent) protocol](https://a2a-protocol.org/).

Expose any smolagents `CodeAgent` as an A2A-compliant server, or delegate tasks from a `CodeAgent` to remote A2A agents.

## Features

- **SmolA2AServer** — Wrap a `CodeAgent` in a FastAPI server that speaks JSON-RPC 2.0 (A2A protocol)
- **SmolA2ADelegateTool** — A `smolagents.Tool` that lets your agent delegate work to any remote A2A agent
- Auto-generated Agent Card for discovery
- SSE streaming support via `message/stream`
- In-memory task store (extensible)

## Installation

```bash
pip install a2a-smol-adapter
```

Or for development:

```bash
git clone https://github.com/matthieu-music/a2a-smol-adapter.git
cd a2a-smol-adapter
pip install -e ".[dev]"
```

## Quick Start

### Expose an agent as A2A server

```python
from smolagents import CodeAgent, InferenceClientModel
from a2a_smol_adapter import SmolA2AServer

agent = CodeAgent(tools=[], model=InferenceClientModel())
server = SmolA2AServer(agent, name="my-agent", port=5001)
server.run()
```

The agent card is available at `http://localhost:5001/.well-known/agent-card.json`.

### Delegate to a remote A2A agent

```python
from smolagents import CodeAgent, InferenceClientModel
from a2a_smol_adapter import SmolA2ADelegateTool

delegate = SmolA2ADelegateTool(remote_url="http://remote-agent:5001/")
agent = CodeAgent(tools=[delegate], model=InferenceClientModel())
result = agent.run("Ask the remote agent to compute pi to 50 digits")
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Remote A2A Client                          │
│  (JSON-RPC 2.0)                             │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  SmolA2AServer                               │
│  ┌────────────────┐  ┌────────────────────┐  │
│  │ A2A FastAPI App │  │ SmolAgentExecutor  │  │
│  │ (JSON-RPC)     │──│ (bridges to smol)  │  │
│  └────────────────┘  └────────────────────┘  │
│                             │                │
│                             ▼                │
│                    ┌─────────────────┐        │
│                    │ smolagents      │        │
│                    │ CodeAgent.run() │        │
│                    └─────────────────┘        │
└──────────────────────────────────────────────┘
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
