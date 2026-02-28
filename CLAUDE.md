# A2A-Smol-Adapter

Bridge library between smolagents (HuggingFace) and the A2A protocol (Linux Foundation).

## Build & Test

```bash
pip install -e ".[dev]"
ruff check src/ tests/              # lint
ruff format src/ tests/              # format
pytest                               # run all tests
pytest tests/test_server.py -v       # single file
pytest -k "test_name"                # single test
```

## Code Style

- Python 3.10+, use `from __future__ import annotations` in every module
- Line length: 100 chars (ruff enforced)
- Type hints on all public functions and method signatures
- Docstrings: Google style, required on all public classes and functions
- Imports: sorted by ruff (isort-compatible)

## Architecture

```
src/a2a_smol_adapter/
├── server.py       # SmolA2AServer + SmolAgentExecutor (A2A → smolagents bridge)
├── client_tool.py  # SmolA2ADelegateTool (smolagents Tool → remote A2A agent)
└── __init__.py     # Public API exports
```

- **server.py**: Receives JSON-RPC 2.0 via FastAPI, translates to `CodeAgent.run()`, returns A2A Artifacts
- **client_tool.py**: smolagents `Tool` subclass that forges JSON-RPC requests to remote A2A agents

## Key Dependencies

- `a2a-sdk[http-server]`: Official A2A Python SDK — use `a2a.types`, `a2a.server.*` classes
- `smolagents`: HuggingFace agent framework — `CodeAgent`, `Tool` base class
- `fastapi` + `uvicorn`: HTTP server (integrated via `A2AFastAPIApplication`)
- `httpx`: HTTP client for the delegation tool

## Testing Rules

- Every public method MUST have at least one test
- Async code: use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock external dependencies (smolagents agent, HTTP calls) — never call real LLMs in tests
- Test error paths: connection failures, malformed JSON-RPC, missing fields
- Use `pytest-httpx` for mocking HTTP client calls

## Conventions

- No print statements — use `logging` module
- Fail fast: validate inputs at function entry, raise `ValueError` with clear messages
- Keep the public API minimal: only `SmolA2AServer` and `SmolA2ADelegateTool` exported
- No backward compatibility hacks — this is pre-1.0, breaking changes are expected
