# Task 6 Report: Guardrail Protocol + PatternGuardrail

## What I Implemented

Created `sentinel/core/guardrails.py` containing:

1. **`Guardrail` protocol** — `@runtime_checkable` Protocol with `name: str` attribute and `check(action, ctx) -> GuardrailResult` method. Enables structural typing/duck-typing checks for any guardrail implementation.

2. **`PatternGuardrail`** — concrete implementation:
   - `name = "pattern"`
   - `__init__(patterns: list[str] | None = None)` — accepts custom patterns, falls back to `DEFAULT_PATTERNS`
   - `check(action, ctx)` — pure function: scans shell text for dangerous patterns, returns `GuardrailResult` with `Decision.DENY` + `RiskLevel.CRITICAL` on match, else `Decision.ALLOW` + `RiskLevel.LOW`
   - All regexes compiled with `re.IGNORECASE`

3. **`DEFAULT_PATTERNS`** — list of dangerous-command regexes:
   - `rm -rf` (recursive force delete)
   - `DROP TABLE` (SQL destruction)
   - `git push --force` / `git push -f` (history rewrite)
   - `curl ... | sh` (pipe-to-shell remote exec)
   - `chmod 777` (world-writable)
   - fork bomb `:(){ :|:& };:`

4. **`_shell_text(action)`** helper — extracts `cmd` from action args and concatenates all `k=v` pairs so patterns match whether they appear in `cmd` or other args.

## TDD Evidence

### RED (Step 2)
```
tests\test_guardrails.py:2: in <module>
    from sentinel.core.guardrails import PatternGuardrail, Guardrail
E   ModuleNotFoundError: No module named 'sentinel.core.guardrails'
============================== 1 error in 0.24s ==============================
```
Test failed for the expected reason (module not yet created), not a typo.

### GREEN (Step 4)
```
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_rf PASSED     [ 16%]
tests/test_guardrails.py::test_pattern_guardrail_denies_drop_table PASSED [ 33%]
tests/test_guardrails.py::test_pattern_guardrail_denies_force_push PASSED [ 50%]
tests/test_guardrails.py::test_pattern_guardrail_allows_pytest PASSED    [ 66%]
tests/test_guardrails.py::test_pattern_guardrail_custom_pattern PASSED   [ 83%]
tests/test_guardrails.py::test_guardrail_is_protocol PASSED              [100%]
============================== 6 passed in 0.04s ==============================
```

### Full Suite (regression check)
```
29 passed in 0.28s
```
No regressions across all prior tasks (types, tools, sandbox, llm).

## Files Changed

| File | Status | Lines |
|------|--------|-------|
| `sentinel/core/guardrails.py` | created | 49 |
| `tests/test_guardrails.py` | created | 32 |

## Commit

```
14997c0 feat(governance): add Guardrail protocol and PatternGuardrail
```

Conventional Commits format (`feat(governance): ...`), consistent with prior task commits (`feat(core): ...`).

## Self-Review Findings

### Verified Against Requirements
- [x] `Guardrail` is `@runtime_checkable` Protocol with `name` and `check`
- [x] `PatternGuardrail.name == "pattern"`
- [x] DENY `rm -rf /` — test passes
- [x] DENY `DROP TABLE` — test passes (case-insensitive: `DROP TABLE` matches inside `psql -c 'DROP TABLE users'`)
- [x] DENY `git push --force` — test passes
- [x] ALLOW `pytest` — test passes (no false positive)
- [x] Custom patterns supported via constructor
- [x] `re.IGNORECASE` applied to all compiled patterns
- [x] Pure function: no LLM, no network, no time effects — `check` depends only on `action` (ctx unused but required by protocol signature for future guardrails)
- [x] Python 3.11+ syntax (`list[str] | None`, `from __future__ import annotations`)
- [x] No agent orchestration frameworks used

### Design Notes
- `_shell_text` concatenates `cmd` plus all `k=v` args, so `cmd` value appears twice in the scanned text. This is intentional and harmless — it widens the match surface so a dangerous token in any arg value is caught.
- `ctx` parameter is unused in `PatternGuardrail.check` but is part of the `Guardrail` protocol contract; future guardrails (e.g. policy-based) may consume it. Keeping it in the signature is correct.

## Concerns

None blocking. Minor observations (not requiring action for this task):

1. **`git push -f` edge case**: pattern `git\s+push\s+(--force|-f)\b` uses `\b` after `-f`, so `git push -force` (no space) would NOT match because `f`→`o` is not a word boundary. This matches the brief verbatim and `git push -force` is not a real git invocation, so acceptable.

2. **`curl|sh` greedy `.*`**: `curl\b.*\|\s*sh` uses greedy `.*` which on a multi-statement command could over-match across statements. For single-line `cmd` strings this is fine; a more robust future pattern could use `[^|]*` but that's a refinement beyond this task's scope.

3. **No `__init__.py` re-export**: `sentinel/core/__init__.py` was not modified to re-export guardrail symbols. Prior tasks (tools, sandbox, llm) also did not re-export, so this is consistent with project convention. Users import from `sentinel.core.guardrails` directly.

All three are forward-looking notes, not defects in the current task.

---

# Task 6 Fix Report: Harden PatternGuardrail (Review Findings 1 & 2)

## Findings Addressed

- **Finding 1 (Important, security-relevant):** `DEFAULT_PATTERNS` only caught literal flag forms; equivalent dangerous commands bypassed the guardrail (`rm -fr /`, `rm -r -f /`, `rm --recursive --force /`, `chmod 0777 file`, `chmod -R 777 file`).
- **Finding 2 (Important):** `test_guardrail_is_protocol` only asserted `hasattr(Guardrail, "check")`, which passes even without `@runtime_checkable`.

## What Changed

### `sentinel/core/guardrails.py` — hardened `DEFAULT_PATTERNS`

Replaced two brittle literal patterns with flag-presence patterns; kept all other patterns (DROP TABLE, git push --force/-f, curl|sh, fork bomb) unchanged.

| Pattern | Before | After |
|---------|--------|-------|
| rm recursive+force | `\brm\s+-rf\b` (literal `-rf` only) | `\brm\b(?=.*(?:--recursive\|\s-[a-z]*r))(?=.*(?:--force\|\s-[a-z]*f))` |
| chmod 777 | `chmod\s+777\b` (literal `777` only) | `\bchmod\b.*\b0*777\b` |

**rm pattern design:** two zero-width lookaheads after `\brm\b` assert that both a recursive flag (`--recursive` or a short cluster containing `r`) and a force flag (`--force` or a short cluster containing `f`) appear later in the command. This catches every equivalent form regardless of flag order, splitting, or long/short style:
- `rm -rf /` (combined, r before f) ✓
- `rm -fr /` (combined, f before r) ✓
- `rm -r -f /` (split) ✓
- `rm -f -r /` (split, reversed) ✓
- `rm --recursive --force /` (long form) ✓
- `rm --force --recursive /` (long form, reversed) ✓

**chmod pattern design:** `\bchmod\b.*\b0*777\b` allows optional flags between `chmod` and the mode (via `.*`) and tolerates leading zeros (`0*777`), catching `chmod 777`, `chmod 0777`, `chmod -R 777`, `chmod -R 0777`.

**Constraints honored:** pure (no LLM/network), `re.IGNORECASE` retained on all compiled patterns, constructor still accepts a custom `patterns` list (hardened set is the new `DEFAULT_PATTERNS`). No new comments added.

### `tests/test_guardrails.py` — strengthened protocol test + new bypass tests

- Strengthened `test_guardrail_is_protocol`: added `assert isinstance(PatternGuardrail(), Guardrail)` to lock the `@runtime_checkable` requirement. Verified this assertion has teeth: without `@runtime_checkable`, `isinstance` raises `TypeError` (not merely returns `False`), so the test would fail/error if the decorator were removed.
- Added 5 new bypass tests (TDD, written first):
  - `test_pattern_guardrail_denies_rm_fr_reordered` — `rm -fr /` → DENY
  - `test_pattern_guardrail_denies_rm_r_f_split` — `rm -r -f /` → DENY
  - `test_pattern_guardrail_denies_rm_long_form` — `rm --recursive --force /` → DENY
  - `test_pattern_guardrail_denies_chmod_0777` — `chmod 0777 file` → DENY
  - `test_pattern_guardrail_denies_chmod_R_777` — `chmod -R 777 file` → DENY

## TDD Evidence

### RED (before hardening — new bypass tests fail for the expected reason)
```
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_fr_reordered FAILED [ 54%]
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_r_f_split FAILED [ 63%]
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_long_form FAILED [ 72%]
tests/test_guardrails.py::test_pattern_guardrail_denies_chmod_0777 FAILED [ 81%]
tests/test_guardrails.py::test_pattern_guardrail_denies_chmod_R_777 FAILED [ 90%]
tests/test_guardrails.py::test_guardrail_is_protocol PASSED              [100%]
========================= 5 failed, 6 passed in 0.23s =========================
```
Each failure: `assert <Decision.ALLOW: 'allow'> == <Decision.DENY: 'deny'>` — i.e. the bypass form was allowed (the defect), not a typo/import error.

### GREEN (after hardening)
```
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_rf PASSED            [  9%]
tests/test_guardrails.py::test_pattern_guardrail_denies_drop_table PASSED       [ 18%]
tests/test_guardrails.py::test_pattern_guardrail_denies_force_push PASSED       [ 27%]
tests/test_guardrails.py::test_pattern_guardrail_allows_pytest PASSED           [ 36%]
tests/test_guardrails.py::test_pattern_guardrail_custom_pattern PASSED          [ 45%]
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_fr_reordered PASSED [ 54%]
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_r_f_split PASSED     [ 63%]
tests/test_guardrails.py::test_pattern_guardrail_denies_rm_long_form PASSED     [ 72%]
tests/test_guardrails.py::test_pattern_guardrail_denies_chmod_0777 PASSED       [ 81%]
tests/test_guardrails.py::test_pattern_guardrail_denies_chmod_R_777 PASSED    [ 90%]
tests/test_guardrails.py::test_guardrail_is_protocol PASSED                    [100%]
============================== 11 passed in 0.05s ==============================
```

### Full Suite (regression check)
```
..................................                                       [100%]
34 passed in 0.32s
```
No regressions (29 prior + 5 new = 34).

### No-False-Positive Spot Check (hardened patterns do not over-match)
```
rm -r file -> allow      (recursive only, no force)
rm -f file -> allow      (force only, no recursive)
rm -i file -> allow      (interactive)
chmod 755 file -> allow
chmod 644 file -> allow
pytest -> allow
ls -la -> allow
```

## Files Changed

| File | Status |
|------|--------|
| `sentinel/core/guardrails.py` | modified (2 patterns hardened) |
| `tests/test_guardrails.py` | modified (5 bypass tests + strengthened protocol test) |

## Commit

```
2c93ddd fix(governance): harden PatternGuardrail against flag-reorder/split/long-form bypasses
```
