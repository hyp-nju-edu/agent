## Task 3: LLM Abstraction + MockLLM

**Files:**
- Create: `sentinel/core/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `LLMProvider` protocol (`async complete(messages, tools) -> LLMResponse`), `LLMResponse`, `MockLLM` (scripts responses from a queue).

- [ ] **Step 1: Write the failing test**

`tests/test_llm.py`:
```python
import pytest
from sentinel.core.llm import LLMProvider, LLMResponse, MockLLM

@pytest.mark.asyncio
async def test_mock_llm_returns_scripted_response():
    mock = MockLLM(responses=[LLMResponse(text="I will run pytest", tool_calls=[])])
    resp = await mock.complete(messages=[{"role": "user", "content": "go"}], tools=[])
    assert resp.text == "I will run pytest"
    assert resp.tool_calls == []

@pytest.mark.asyncio
async def test_mock_llm_raises_when_empty():
    mock = MockLLM(responses=[])
    with pytest.raises(RuntimeError, match="no more scripted responses"):
        await mock.complete(messages=[], tools=[])

@pytest.mark.asyncio
async def test_mock_llm_yields_tool_calls():
    calls = [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    mock = MockLLM(responses=[LLMResponse(text="", tool_calls=calls)])
    resp = await mock.complete(messages=[], tools=[])
    assert resp.tool_calls == calls

def test_llm_provider_is_protocol():
    assert hasattr(LLMProvider, "complete")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_llm.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/llm.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    async def complete(self, messages: list[dict[str, Any]],
                        tools: list[dict[str, Any]]) -> LLMResponse: ...


class MockLLM:
    """Deterministic LLM that returns scripted responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        if self._index >= len(self._responses):
            raise RuntimeError("no more scripted responses")
        r = self._responses[self._index]
        self._index += 1
        return r
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_llm.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/llm.py tests/test_llm.py
git commit -m "feat(core): add LLMProvider protocol and MockLLM"
```

---

