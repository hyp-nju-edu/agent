## Task 4: Tool Layer + ToolRegistry

**Files:**
- Create: `sentinel/core/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `Action`, `ToolResult` from `types`.
- Produces: `Tool` protocol (`name`, `risk_level`, `execute(args, sandbox) -> ToolResult`), `ToolRegistry`.

- [ ] **Step 1: Write the failing test**

`tests/test_tools.py`:
```python
import pytest
from sentinel.core.types import Action, ToolResult, RiskLevel
from sentinel.core.tools import Tool, ToolRegistry

class EchoTool:
    name = "echo"
    risk_level = RiskLevel.LOW
    async def execute(self, args, sandbox):
        return ToolResult(success=True, stdout=str(args.get("msg", "")))

@pytest.mark.asyncio
async def test_tool_executes():
    t = EchoTool()
    r = await t.execute({"msg": "hi"}, sandbox=None)
    assert r.success and r.stdout == "hi"

def test_registry_get_returns_tool():
    reg = ToolRegistry([EchoTool()])
    assert reg.get("echo").name == "echo"

def test_registry_get_unknown_raises():
    reg = ToolRegistry([EchoTool()])
    import pytest
    with pytest.raises(KeyError):
        reg.get("nope")

def test_registry_lists_names():
    reg = ToolRegistry([EchoTool()])
    assert reg.names() == ["echo"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_tools.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/tools.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, RiskLevel, ToolResult


class SandboxBackend(Protocol):
    async def run(self, command: list[str], cwd: str | None = None) -> ToolResult: ...
    async def read_file(self, path: str) -> ToolResult: ...
    async def write_file(self, path: str, content: str) -> ToolResult: ...


@runtime_checkable
class Tool(Protocol):
    name: str
    risk_level: RiskLevel
    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult: ...


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_tools.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/tools.py tests/test_tools.py
git commit -m "feat(core): add Tool protocol and ToolRegistry"
```

---

