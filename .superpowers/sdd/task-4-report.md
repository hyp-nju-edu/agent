# Task 4 Report: Tool Layer + ToolRegistry

## What I Implemented

Created `sentinel/core/tools.py` with three components per the task brief:

1. **`SandboxBackend` Protocol** — defines the sandbox contract for later tasks:
   - `async run(command, cwd=None) -> ToolResult`
   - `async read_file(path) -> ToolResult`
   - `async write_file(path, content) -> ToolResult`

2. **`Tool` Protocol** (`@runtime_checkable`) — the tool interface:
   - `name: str`
   - `risk_level: RiskLevel`
   - `async execute(args: dict, sandbox: SandboxBackend) -> ToolResult`

3. **`ToolRegistry`** — name-indexed tool lookup:
   - `__init__(tools: list[Tool])` builds `{t.name: t}` dict
   - `get(name)` returns tool or raises `KeyError(f"unknown tool: {name}")`
   - `names()` returns list of registered tool names

Created `tests/test_tools.py` with 4 tests verbatim from the brief:
- `test_tool_executes` (async) — EchoTool.execute returns ToolResult
- `test_registry_get_returns_tool` — lookup by name
- `test_registry_get_unknown_raises` — KeyError on unknown
- `test_registry_lists_names` — names() returns registered names

## TDD Evidence

### RED (before implementation)
```
ImportError while importing test module 'tests\test_tools.py'.
E   ModuleNotFoundError: No module named 'sentinel.core.tools'
ERROR tests/test_tools.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

### GREEN (after implementation)
```
tests/test_tools.py::test_tool_executes PASSED                           [ 25%]
tests/test_tools.py::test_registry_get_returns_tool PASSED               [ 50%]
tests/test_tools.py::test_registry_get_unknown_raises PASSED             [ 75%]
tests/test_tools.py::test_registry_lists_names PASSED                    [100%]
============================= 4 passed in 0.04s ==============================
```

### Full suite (no regressions)
```
============================= 18 passed in 0.06s ==============================
```

## Files Changed

- `sentinel/core/tools.py` (new, 31 lines)
- `tests/test_tools.py` (new, 28 lines)

## Commit

- `de6777f` — `feat(core): add Tool protocol and ToolRegistry`

## Self-Review Findings

1. **`Tool` is `@runtime_checkable`** as required — `isinstance(obj, Tool)` works via structural matching (method/attr names only, not signatures).
2. **`ToolRegistry.get(unknown)` raises `KeyError`** with a descriptive message — verified by `test_registry_get_unknown_raises`.
3. **Python 3.11+ compatible** — uses `from __future__ import annotations`, `list[str]`, `str | None`.
4. **No agent orchestration frameworks** — only stdlib (`typing`) and internal `sentinel.core.types`.
5. **Conventional Commits** — `feat(core): ...` matches prior commit style (`feat(core): add LLMProvider...`).
6. **Tests match brief verbatim** including the inner `import pytest` in `test_registry_get_unknown_raises` (redundant but per spec).

## Concerns

1. **`Action` imported but unused in `tools.py`** — the brief's import line includes `Action` (listed under "Consumes" interface), but it isn't referenced in the implementation body. No linter is configured in this repo, so it won't fail CI, but a strict linter (ruff F401) would flag it. Left as-is to match the brief exactly.

2. **`SandboxBackend` is untested** — it's a forward-looking protocol for later sandbox tasks. No tests exercise it (per brief, which only tests `Tool` and `ToolRegistry`). Will be validated when concrete sandbox backends are implemented.

3. **`@pytest.mark.asyncio` decorators are technically redundant** — `pyproject.toml` sets `asyncio_mode = "auto"`, so async tests are collected automatically. Kept the decorators to match the brief verbatim.

4. **`EchoTool` lacks type annotations** on `execute` — it still satisfies the `Tool` protocol structurally because `@runtime_checkable` protocols only check attribute/method existence, not signatures. This is fine for the test fixture and matches the brief.

No blocking issues. Implementation is minimal, correct, and matches the brief exactly.
