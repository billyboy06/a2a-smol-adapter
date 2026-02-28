# Testing Standards

## Mandatory Coverage

- Every new public function or method MUST ship with tests
- Every bug fix MUST include a regression test
- No code is considered complete until tests pass: `pytest` must exit 0

## Test Organization

- Unit tests in `tests/` mirroring `src/` structure
- Integration tests in `tests/integration/` (optional, for end-to-end flows)
- Shared fixtures in `tests/conftest.py`

## Mocking Strategy

- NEVER call real LLM APIs in tests — always mock `CodeAgent.run()`
- NEVER make real HTTP calls — use `pytest-httpx` or `unittest.mock`
- Mock at the boundary: mock the external dependency, not internal logic
- Use `MagicMock(spec=ClassName)` to catch interface changes

## Async Testing

- Use `pytest-asyncio` with `asyncio_mode = "auto"`
- Async fixtures: use `@pytest.fixture` with `async def`
- Test both success and failure paths for async operations
- Test cancellation behavior where applicable

## What NOT to Test

- Private methods directly (test them through public API)
- Third-party library behavior
- Simple data classes with no logic
- Obvious getters/setters

## Test Quality Checklist

Before considering tests complete:
- [ ] Happy path covered
- [ ] Error/edge cases covered (empty input, None, malformed data)
- [ ] Async error paths tested (timeouts, connection failures)
- [ ] No flaky tests (no sleep-based timing, no external dependencies)
- [ ] Tests run in isolation (no shared mutable state between tests)
