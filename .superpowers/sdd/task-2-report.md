# Task 2: Core Types — Report

## What I Implemented

Created `sentinel/core/types.py` with the 12 foundational data types that later modules import:

- **Enums** (`str, Enum`): `RiskLevel` (LOW/MEDIUM/HIGH/CRITICAL), `Decision` (ALLOW/DENY/REQUIRE_APPROVAL), `ApprovalDecision` (APPROVED/DENIED), `FailureKind` (5 variants).
- **Dataclasses**: `Action` (auto-generated `id` via `uuid4().hex`), `GuardrailResult`, `ToolResult` (with `dict` default factory), `Failure`, `Feedback`, `Event`, `Approval`, `RunContext`.

Created `tests/test_types.py` with 9 tests verbatim from the brief.

## TDD Evidence

### RED (Step 2)

Command:
```
python -m pytest tests/test_types.py -v
```
Result: collection error — `ModuleNotFoundError: No module named 'sentinel.core.types'` (0 collected, 1 error). Confirms the test fails before implementation exists.

### GREEN (Step 4)

Command:
```
python -m pytest tests/test_types.py -v
```
Result: `9 passed in 0.04s`. Full suite (`python -m pytest -v`) also reports `9 passed` — no regressions.

## Deviation From the Brief (with justification)

The brief's `RiskLevel` implementation defines **only `__lt__`**, but the brief's test asserts `RiskLevel.CRITICAL > RiskLevel.MEDIUM` (the `>` operator). The brief's verbatim code fails this test.

**Root cause** (investigated via systematic-debugging skill): `RiskLevel` subclasses `(str, Enum)`. Python resolves `>` to `str.__gt__`, which compares the string values alphabetically — `"critical" > "medium"` is `False` because `"c" < "m"`. The custom `__lt__` only intercepts `<`.

**Failed fix attempt #1:** Added `@functools.total_ordering`. Did NOT work — verified `RiskLevel.__gt__ is str.__gt__` returned `True`. `total_ordering` only fills in ordering methods that are *not already defined*; since `str` provides `__gt__`/`__le__`/`__ge__`, the decorator silently skips them.

**Fix attempt #2 (applied):** Added an explicit `__gt__` method mirroring `__lt__`'s order-map approach. This is the minimal change that keeps the brief's `__lt__` intact and makes the test pass. Removed the unused `total_ordering` import to avoid dead/misleading code.

## Files Changed

- `sentinel/core/types.py` (new, 104 lines)
- `tests/test_types.py` (new, 52 lines)

## Commits

- `f802bae` — `feat(core): add core types (Action, Decision, GuardrailResult, Feedback, Event)`

## Self-Review Findings

### Completeness
- All 12 interfaces listed in the brief are present and exported by the module.
- All 9 tests from the brief are present verbatim and passing.

### Quality
- Implementation matches the brief verbatim except for the necessary `__gt__` addition (justified above).
- Style is consistent: `(str, Enum)` for all enums, `@dataclass` for all value types, `field(default_factory=...)` for mutables.

### YAGNI
- Added only `__gt__` (required by the test). Did **not** add `__le__`/`__ge__` since no test exercises them — adding untested code would violate TDD. If a later task needs `<=`/`>=`, it should add the method *and* a failing test together.
- No extra fields, classes, or methods beyond the brief.

### Testing
- 9/9 passing. Tests cover: Action auto-id & defaults, Decision values, RiskLevel ordering (both `<` and `>`), GuardrailResult fields, ToolResult defaults (incl. mutable `artifacts` default), Feedback nullable `passed`, Event data access, RunContext task/turns, ApprovalDecision values.

## Concerns

1. **Latent `<=`/`>=` bug:** `RiskLevel.__le__` and `__ge__` are not overridden, so they fall back to `str` comparison (alphabetical, not semantic). `RiskLevel.LOW <= RiskLevel.HIGH` happens to be True (because `"low" <= "high"` is False alphabetically — actually it would be **wrong**). Any later code using `<=`/`>=` on `RiskLevel` will get incorrect results. Recommend a follow-up task add `__le__`/`__ge__` (or a shared order helper) with tests if any later module needs them.
2. **Duplicated order map:** The `{RiskLevel.LOW: 0, ...}` dict is repeated in `__lt__` and `__gt__`. A small refactor (class-level `_ORDER` mapping or a helper) would remove the duplication, but that exceeds the minimal-fix scope for this task.
3. **Brief inconsistency:** The brief's provided implementation did not satisfy the brief's provided test. Flagging in case the plan author wants to reconcile the brief for future runs.

---

# Task 2 Review Fix — Report

## Findings Addressed

1. **Important — `RiskLevel.__le__`/`__ge__` broken.** `<=`/`>=` fell back to `str` alphabetical comparison (e.g. `RiskLevel.LOW <= RiskLevel.HIGH` → False; `RiskLevel.CRITICAL <= RiskLevel.MEDIUM` → True), which would let a CRITICAL risk wrongly pass a HIGH/MEDIUM threshold check — security-relevant for governance guardrails.
2. **Minor — duplicated order map.** The `{RiskLevel.LOW: 0, ...}` dict was defined identically in both `__lt__` and `__gt__`, so the two could drift apart.

## What Changed

In `sentinel/core/types.py`:
- Added a class-level `_ORDER` mapping (`{RiskLevel.LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3}`), assigned **after** class creation (`RiskLevel._ORDER = {...}`) so the `Enum` metaclass does not consume it as a member (an in-body `_ORDER = {...}` was verified to be coerced into a `str`-Enum member, causing `TypeError: string indices must be integers`).
- Rewrote `__lt__` and `__gt__` to use `self._ORDER[...]` (semantics identical: `LOW < HIGH` is True).
- Added `__le__` and `__ge__` using the same `_ORDER` map.
- Did NOT change the `(str, Enum)` base or the `.value` strings ("low"/"medium"/"high"/"critical").

In `tests/test_types.py`:
- Added `test_risk_level_le_ge` covering the four required cases (`LOW <= HIGH` True, `CRITICAL <= MEDIUM` False, `HIGH >= LOW` True, `MEDIUM >= CRITICAL` False). Assertions parenthesized (`(a <= b) is True`) because `is` binds tighter than `<=`.
- Kept existing `test_risk_level_ordering` (`<`/`>`) unchanged and passing.

## TDD Evidence

### RED (before fix)

Command:
```
python -m pytest tests/test_types.py -v
```
Result: `1 failed, 9 passed` — `test_risk_level_le_ge` failed on the first assertion with `assert (<RiskLevel.LOW: 'low'> <= <RiskLevel.HIGH: 'high'>) is True`, confirming `<=` returned the wrong value (str alphabetical comparison). Existing `test_risk_level_ordering` still passed.

### GREEN (after fix)

Command:
```
python -m pytest tests/test_types.py -v
```
Result: `10 passed in 0.04s` — all old + new tests green.

### Full suite

Command:
```
python -m pytest -q
```
Result: `10 passed in 0.03s` — no regressions.

## Files Changed

- `sentinel/core/types.py` (modified: +16/-6)
- `tests/test_types.py` (modified: +6/-0)

## Commit

- `ec0f0cd` — `fix(core): complete RiskLevel ordering (__le__/__ge__) and dedupe order map`
