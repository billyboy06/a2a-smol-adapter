# smolagents Conventions

## Tool Subclassing

- Inherit from `smolagents.Tool`
- Required class attributes: `name`, `description`, `inputs`, `output_type`
- Implement `forward()` method — this is the execution entry point
- `inputs` is a dict mapping param names to `{"type": "string", "description": "..."}`
- `output_type` is a string: `"string"`, `"number"`, `"boolean"`, `"image"`, `"audio"`
- Call `super().__init__(**kwargs)` in `__init__`

## CodeAgent Integration

- `CodeAgent.run(prompt)` is synchronous — wrap in `asyncio.run_in_executor` for async contexts
- Never modify the agent's tools list after initialization
- Agent generates and executes Python code — output can be any type, always `str()` it for A2A

## Error Handling

- smolagents exceptions propagate from `agent.run()` — catch and translate to A2A error responses
- Tool `forward()` should return error strings, not raise exceptions (smolagents convention)
- If the agent fails, return a `TaskStatusUpdateEvent` with `state=failed`
