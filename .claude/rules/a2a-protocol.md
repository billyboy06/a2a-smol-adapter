# A2A Protocol Conventions

## SDK Usage

- Use `a2a.types` for all A2A data models — never define custom JSON-RPC types
- Use `A2AFastAPIApplication` for server setup — don't build raw FastAPI routes
- Use `DefaultRequestHandler` with custom `AgentExecutor` — don't implement `RequestHandler` from scratch
- Use `InMemoryTaskStore` for development — plan for pluggable stores later

## JSON-RPC 2.0

- Method names follow A2A spec: `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`
- Always include `jsonrpc: "2.0"` and unique `id` in requests
- Error responses use standard JSON-RPC error codes
- Message parts use `kind` discriminator: `"text"`, `"file"`, `"data"`

## Agent Card

- Served at `/.well-known/agent-card.json` (standard discovery endpoint)
- Must include: `name`, `description`, `version`, `url`, `capabilities`, `skills`
- Skills describe what the agent can do — keep descriptions actionable
- `defaultInputModes` and `defaultOutputModes` declare supported MIME types

## Task Lifecycle

- States: `submitted` → `working` → `completed` | `failed` | `canceled`
- Always emit `TaskStatusUpdateEvent` before and after agent execution
- Final event MUST have `final=True`
- Artifacts are attached via `TaskArtifactUpdateEvent`

## Streaming (SSE)

- Use `message/stream` method for streaming responses
- Yield `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent` as events
- Support `tasks/resubscribe` for reconnection to active streams
