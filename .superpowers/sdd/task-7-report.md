# Task 7 Report: ScopeFence + SandboxBoundary + RiskClassifier Guardrails

## Status: DONE

## What I Implemented

Appended three guardrails to `sentinel/core/guardrails.py` (following the brief verbatim):

1. **`ScopeFenceGuardrail`** — path boundary enforcement.
   - Constructor takes a `workspace` path (resolved via `Path.resolve()`).
   - `_is_within()` joins the action path onto the workspace and resolves it, then checks the result is the workspace itself or a descendant (in `p.parents`). This makes `../../` escapes resolve to a path outside the workspace → DENY.
   - `_is_sensitive()` checks the path against `SENSITIVE_GLOBS` (`**/.env`, `**/.aws/*`, `**/.ssh/*`, `**/credentials*`, `**/*.key`, `**/*.pem`) using `fnmatch`, testing both the raw path and a `/`-prefixed form so bare names like `.env` match.
   - `check()` order: no path → ALLOW; sensitive → DENY (CRITICAL); outside workspace → DENY (HIGH); otherwise ALLOW (LOW).

2. **`SandboxBoundaryGuardrail`** — network action flagger.
   - Reuses the existing `_shell_text(action)` helper.
   - Scans for `NETWORK_HINTS` (`pip install`, `curl `, `wget `, `git clone`, `npm install`, `http://`, `https://`).
   - Match → `REQUIRE_APPROVAL` (HIGH) with reason containing "network"; else ALLOW (LOW).

3. **`RiskClassifierGuardrail`** — per-tool risk assignment.
   - Looks up `action.tool` in `TOOL_RISK` (`read_file`/`list_dir`/`search`=LOW, `write_file`/`run_tests`=MEDIUM, `run_shell`=HIGH); unknown tools default to MEDIUM.
   - Always ALLOWs (it classifies, doesn't gate).

Added imports (`Path`, `fnmatch`) at the top of the module.

## TDD Evidence

- **RED**: After appending the 8 new tests, `python -m pytest tests/test_guardrails.py -v` failed during collection with `ImportError: cannot import name 'ScopeFenceGuardrail' from 'sentinel.core.guardrails'`.
- **GREEN**: After appending the implementation, all 19 tests in `tests/test_guardrails.py` pass (11 pre-existing PatternGuardrail tests + 8 new). Full suite: 42 passed.

## Files Changed

- `sentinel/core/guardrails.py` — added `Path`/`fnmatch` imports; appended `SENSITIVE_GLOBS`, `ScopeFenceGuardrail`, `NETWORK_HINTS`, `SandboxBoundaryGuardrail`, `TOOL_RISK`, `RiskClassifierGuardrail`.
- `tests/test_guardrails.py` — added import of the three new guardrails; appended 8 test functions.

## Commits

- `3b2311a` feat(governance): add ScopeFence, SandboxBoundary, RiskClassifier guardrails

## Self-Review Findings

- **Pure functions**: All three guardrails are pure functions of `(action, ctx)` — no LLM, no network, no time effects. ✓
- **`../../` escape robustness**: `_is_within` uses `Path.resolve()` which lexically normalizes `..` segments, so escapes resolve to a path outside the workspace and are denied. Verified by `test_scope_fence_denies_out_of_workspace_write`. ✓
- **Sensitive reads**: `.env` and `~/.ssh/id_rsa` both denied before the workspace check runs (sensitive check is first). ✓
- **In-workspace writes allowed**: `src/main.py` resolves under the workspace → ALLOW. ✓
- **No regression**: All 11 Task-6 PatternGuardrail tests still pass; full suite (42 tests) green. ✓
- **Protocol conformance**: All three new classes satisfy the `Guardrail` Protocol (have `name: str` and `check(action, ctx) -> GuardrailResult`).

## Concerns

- **Windows path semantics**: The brief uses `workspace="/tmp/ws"`. On Windows, `Path("/tmp/ws")` is drive-relative (resolves to `<current_drive>:\tmp\ws`), not a POSIX absolute. Tests pass because resolution is internally consistent (workspace and joined path use the same drive), but a caller passing a POSIX-style absolute on Windows may get drive-relative behavior. This is inherent to the brief's spec and Python's `pathlib` on Windows; not altered.
- **`_shell_text` includes `cmd=...`**: The existing helper (from Task 6) appends `key=value` pairs to the scanned text, so a command whose arguments contain a network hint string (e.g. `echo cmd=pip install`) could trigger a false positive. This is pre-existing behavior in the shared helper, not introduced by this task, and matches the brief's spec.
- **`fnmatch` `*` matches `/`**: `fnmatch`'s `*` matches path separators, so `**/.env` matches `a/b/.env` (intended for sensitive-file detection). This is the desired behavior for the sensitive-glob check.
- **`NETWORK_HINTS` substring matching**: Hints like `curl ` (trailing space) and `http://` are substring matches, which could in theory false-positive on benign strings containing those substrings. Acceptable per brief; the decision is REQUIRE_APPROVAL (not DENY), so a human can still approve.
