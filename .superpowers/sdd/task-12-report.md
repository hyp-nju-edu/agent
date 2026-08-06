# Task 12: Feedback Validators — Report

## What I Implemented

Created `sentinel/core/feedback.py` with:

- **`Validator`** — `@runtime_checkable` `Protocol` with a single method
  `parse(self, tool_result: ToolResult, action: Action) -> Feedback`.
- **`PytestValidator`** — deterministic regex classifier:
  - `SyntaxError` (case-insensitive) → `FailureKind.SYNTAX_ERROR`
  - `ModuleNotFoundError|ImportError` → `FailureKind.IMPORT_ERROR`
  - `FAILED <nodeid> - <msg>` lines → `FailureKind.ASSERTION_FAILURE`
  - `passed` is forced to `False` whenever any failure is detected; otherwise
    follows `tool_result.success` (with a fallback to scanning for `"passed"`
    in output when exit code was non-zero but no failures matched).
- **`RuffValidator`** — parses `path:line:col CODE message` lines into
  `FailureKind.UNKNOWN` failures carrying `location`.
- **`MypyValidator`** — parses `path:line: error: message` lines into
  `FailureKind.TYPE_ERROR` failures carrying `location`.
- **`select_validator(action)`** — `run_tests` → `PytestValidator`;
  `cmd` containing `"ruff"` → `RuffValidator`; `"mypy"` → `MypyValidator`;
  falls back to `PytestValidator`.

All validators concatenate `stdout + "\n" + stderr` before parsing, so
diagnostics on either stream are observed. No LLM calls — fully deterministic.

## TDD Evidence

- **RED:** `tests/test_feedback.py` written first; `python -m pytest
  tests/test_feedback.py -v` failed during collection with
  `ModuleNotFoundError: No module named 'sentinel.core.feedback'`.
- **GREEN:** After implementing `sentinel/core/feedback.py`, the same
  command reports `9 passed in 0.10s`.
- **Full suite:** `python -m pytest -q` → `76 passed in 0.33s` (no
  regressions across tasks 2–11).

## Files Changed

- `sentinel/core/feedback.py` (new, 60 lines)
- `tests/test_feedback.py` (new, 43 lines, 9 tests — verbatim from brief)

## Commits

- `0becacd` — `feat(feedback): add pytest/ruff/mypy validators and selector`

## Self-Review Findings

- Implementation matches the brief verbatim; no deviations.
- `Validator` is `@runtime_checkable`, so `isinstance(x, Validator)` works
  structurally; the tests instead check against the concrete classes
  (`PytestValidator`, etc.), which is stricter and also fine.
- `PytestValidator.passed` logic is intentionally defensive: any detected
  failure forces `passed=False` even if `tool_result.success` were `True`
  (e.g., a SyntaxError surfacing in stdout despite a zero exit). This is
  safer than trusting the exit code alone.
- `RuffValidator`/`MypyValidator` trust `tool_result.success` for `passed`
  and only enrich `failures` from output, per brief.
- Determinism confirmed: no I/O, no randomness, no LLM — pure regex parsing.
- `from __future__ import annotations` is present so the `Validator` return
  annotation in `select_validator` resolves cleanly under 3.11+.

## Concerns

- **Minor:** `select_validator` falls back to `PytestValidator` for unknown
  `run_shell` commands (e.g., `pytest` invoked via shell, or unrelated
  commands). The brief specifies this fallback, but a real harness may prefer
  returning `None`/raising for unrecognized commands to avoid
  misclassification. Flagging for future task owners; not changing per brief.
- **Minor:** `PytestValidator`'s `passed` expression
  (`tool_result.success if tool_result.success else (not failures and
  "passed" in out)`) is slightly convoluted but is the brief's verbatim
  form; left untouched.
- No concerns blocking completion.
