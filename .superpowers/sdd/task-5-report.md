# Task 5 Report: InProcessSandbox Backend

## What I Implemented

Created `sentinel/core/sandbox.py` with the `InProcessSandbox` class — a restricted working-directory sandbox that enforces path boundaries. The class implements the `SandboxBackend` protocol (structurally; the protocol is not `@runtime_checkable`).

### API
- `__init__(workspace: str)` — resolves & creates the workspace dir.
- `_resolve(path: str) -> Path` — joins path to workspace, resolves symlinks/`..`, raises `PermissionError("...denied...")` if the result escapes the workspace.
- `async run(command, cwd=None) -> ToolResult` — runs a subprocess in the workspace (60s timeout), captures stdout/stderr.
- `async read_file(path) -> ToolResult` — boundary-checked read.
- `async write_file(path, content) -> ToolResult` — boundary-checked write (creates parent dirs).

### Path Boundary Logic
```python
p = (self.workspace / path).resolve()
if self.workspace not in p.parents and p != self.workspace:
    raise PermissionError(f"path outside workspace denied: {path}")
```
Uses `.resolve()` to normalize `../../` escapes before the boundary check. Errors are caught and returned as `ToolResult(success=False, error=...)` with "denied" in the message.

## TDD Evidence

### RED (before implementation)
```
ModuleNotFoundError: No module named 'sentinel.core.sandbox'
1 error in 0.25s
```

### GREEN (after implementation)
```
tests/test_sandbox.py::test_run_echo PASSED                              [ 20%]
tests/test_sandbox.py::test_run_failure_captured PASSED                  [ 40%]
tests/test_sandbox.py::test_write_and_read_file PASSED                   [ 60%]
tests/test_sandbox.py::test_read_outside_workspace_denied PASSED         [ 80%]
tests/test_sandbox.py::test_write_outside_workspace_denied PASSED        [100%]
5 passed in 0.25s
```

### Full suite (no regressions)
```
23 passed in 0.28s
```

## Files Changed
- `sentinel/core/sandbox.py` (new, 49 lines)
- `tests/test_sandbox.py` (new, 40 lines)

## Commit
- `91ee50c feat(core): add InProcessSandbox with path boundary enforcement`

## Self-Review Findings

### Strengths
- Implementation matches the brief verbatim.
- Path boundary check correctly uses `.resolve()` before comparison, defeating `../../` escapes.
- All 5 brief tests pass; all 23 tests in the full suite pass (no regressions in Tasks 1–4).
- `ToolResult` is used consistently for both success and failure paths.
- Conventional Commit message follows the repo style (`feat(core): ...`).

### Concerns / Notes
1. **Blocking subprocess in async**: `run()` uses `subprocess.run` (synchronous) inside an `async` function. This blocks the event loop for up to 60s. A production version should use `asyncio.create_subprocess_exec`. This matches the brief verbatim, so it's per spec — flagging for a future hardening task.
2. **`cwd` parameter ignored**: `run(command, cwd=None)` accepts `cwd` but always uses `self.workspace`. Per the brief; documented here so it isn't mistaken for a bug later.
3. **`os` import unused**: The brief's code imports `os` but never uses it. Left as-is to match the brief verbatim; a linter would flag it.
4. **Windows path semantics**: On Windows, `../../etc/passwd` resolves to a path outside the workspace (e.g. `E:\etc\passwd`), which the boundary check denies before any filesystem access is attempted — so the test passes deterministically regardless of whether the target file exists.
5. **Protocol not runtime-checkable**: `SandboxBackend` is a plain `Protocol` (not `@runtime_checkable`), so `isinstance(sb, SandboxBackend)` raises `TypeError`. Structural compatibility is verified by signature match; this is consistent with Task 4's design and not a defect.

## Conclusion
Status: **DONE**. All brief tests green, full suite green, committed. Concerns are notes for future hardening, not blockers for this task.
