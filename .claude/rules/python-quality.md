# Python Code Quality

## Type Hints

- All public functions and methods MUST have type annotations (parameters + return type)
- Use `from __future__ import annotations` for modern syntax (PEP 604 unions, etc.)
- Use `|` union syntax instead of `Optional[]` or `Union[]`
- Collections: use built-in generics (`list[str]`, `dict[str, Any]`) not `typing.List`
- For complex types, define `TypeAlias` at module level

## Error Handling

- Validate inputs at function entry — fail fast with `ValueError` and descriptive message
- Never catch bare `except:` or `except Exception:` without re-raising or specific handling
- Use specific exception types: `ValueError`, `TypeError`, `ConnectionError`
- Log errors before raising when context would be lost
- No silent failures: every error path must either raise, log, or return an explicit error value

## Naming

- Classes: `PascalCase`
- Functions/methods/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: prefix with `_` (single underscore)
- No abbreviations in public API names

## Structure

- One class per module when the class is substantial (>50 lines)
- Helper functions: private (`_func`) in the same module, not in a separate `utils.py`
- Imports at top of file, grouped: stdlib → third-party → local (ruff enforces this)
- No circular imports — if needed, restructure or use lazy imports

## Docstrings (Google Style)

```python
def process(data: list[dict], strict: bool = False) -> TraceData:
    """Parse raw trace entries into structured data.

    Args:
        data: List of JSON-RPC trace entries.
        strict: If True, raise on malformed entries instead of skipping.

    Returns:
        Parsed trace data with interactions and agent metadata.

    Raises:
        ValueError: If data is empty or contains no valid entries.
    """
```

## Testing

- Test file mirrors source: `src/pkg/server.py` → `tests/test_server.py`
- Test class per source class: `class TestSmolA2AServer:`
- Test method naming: `test_<scenario>` — descriptive, no abbreviations
- Arrange-Act-Assert pattern
- One assertion per concept (multiple asserts OK if testing same logical thing)
- Use `pytest.raises` for expected exceptions, not try/except
- Fixtures over setup methods when state is shared across tests
