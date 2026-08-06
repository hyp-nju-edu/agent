# Task 3 Report: LLM Abstraction + MockLLM

## Status: DONE

## What I Implemented

Created `sentinel/core/llm.py` with three components, verbatim from the task brief:

1. **`LLMResponse`** — a dataclass with `text: str = ""` and `tool_calls: list[dict[str, Any]]` (default factory → empty list). Represents a single LLM completion result.
2. **`LLMProvider`** — a `typing.Protocol` defining the provider interface: `async complete(messages, tools) -> LLMResponse`. Enables structural subtyping so `MockLLM` (and future real providers) conform without explicit inheritance.
3. **`MockLLM`** — a deterministic test double that scripts responses from a queue. `__init__` copies the response list (defensive copy) and initializes an index counter. `complete()` returns the next scripted `LLMResponse` in order, or raises `RuntimeError("no more scripted responses")` when the queue is exhausted. No randomness → reproducible tests.

Created `tests/test_llm.py` with 4 tests (verbatim from brief):
- `test_mock_llm_returns_scripted_response` — single scripted text response is returned.
- `test_mock_llm_raises_when_empty` — empty queue raises `RuntimeError` matching `"no more scripted responses"`.
- `test_mock_llm_yields_tool_calls` — scripted tool calls are passed through.
- `test_llm_provider_is_protocol` — `LLMProvider` exposes a `complete` attribute.

## TDD Evidence

### RED (Step 2) — before implementation
```
ImportError while importing test module 'E:\agent\tests\test_llm.py'.
E   ModuleNotFoundError: No module named 'sentinel.core.llm'
============================== 1 error in 0.29s ==============================
```
Confirmed failure mode matches brief's expectation (`ModuleNotFoundError`).

### GREEN (Step 4) — after implementation
```
tests/test_llm.py::test_mock_llm_returns_scripted_response PASSED        [ 25%]
tests/test_llm.py::test_mock_llm_raises_when_empty PASSED                [ 50%]
tests/test_llm.py::test_mock_llm_yields_tool_calls PASSED                [ 75%]
tests/test_llm.py::test_llm_provider_is_protocol PASSED                  [100%]
============================== 4 passed in 0.05s ==============================
```

### Full suite (no regressions)
```
14 passed in 0.06s
```
All 10 pre-existing `test_types.py` tests still pass alongside the 4 new tests.

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `sentinel/core/llm.py` | Created | +30 |
| `tests/test_llm.py` | Created | +25 |
| **Total** | | **+55** |

## Commit

```
58aa1c4 feat(core): add LLMProvider protocol and MockLLM
```
Conventional Commits format, scope `core`, type `feat`. Working tree clean after commit.

## Self-Review Findings

- **Determinism**: `MockLLM` uses a monotonic index counter and no RNG — fully reproducible. ✅
- **Defensive copy**: `__init__` does `list(responses)`, so external mutation of the caller's list after construction won't corrupt the queue. ✅
- **Protocol conformance**: `MockLLM` does not explicitly inherit from `LLMProvider` — correct for structural subtyping with `typing.Protocol`. The signature of `MockLLM.complete` matches the protocol exactly. ✅
- **Exhaustion error**: `RuntimeError` message is `"no more scripted responses"`, matching the test's regex `match="no more scripted responses"`. ✅
- **Defaults**: `LLMResponse` uses `field(default_factory=list)` for `tool_calls`, avoiding the mutable-default-argument pitfall. ✅
- **No regressions**: full 14-test suite passes. ✅
- **Code style**: matches existing `types.py` conventions (`from __future__ import annotations`, dataclasses, `Any` typing). ✅

## Concerns

None. Implementation is verbatim from the brief, tests pass, no regressions, commit is clean.

Minor note (not a concern for this task): `LLMProvider` is not decorated with `@runtime_checkable`, so `isinstance()` checks against it won't work — but the brief neither requires nor tests this, and structural subtyping via signature matching works as intended.
