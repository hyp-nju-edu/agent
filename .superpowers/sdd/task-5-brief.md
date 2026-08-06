## Task 5: InProcessSandbox Backend

**Files:**
- Create: `sentinel/core/sandbox.py`
- Test: `tests/test_sandbox.py`

**Interfaces:**
- Consumes: `ToolResult` from `types`, `SandboxBackend` protocol from `tools`.
- Produces: `InProcessSandbox` (restricted working dir; enforces path boundaries).

- [ ] **Step 1: Write the failing test**

`tests/test_sandbox.py`:
```python
import pytest
from sentinel.core.sandbox import InProcessSandbox

@pytest.mark.asyncio
async def test_run_echo(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.run(["python", "-c", "print('hi')"])
    assert r.success and "hi" in r.stdout

@pytest.mark.asyncio
async def test_run_failure_captured(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.run(["python", "-c", "import sys; sys.exit(2)"])
    assert not r.success

@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    w = await sb.write_file("sub/a.txt", "hello")
    assert w.success
    r = await sb.read_file("sub/a.txt")
    assert r.success and r.stdout == "hello"

@pytest.mark.asyncio
async def test_read_outside_workspace_denied(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.read_file("../../etc/passwd")
    assert not r.success
    assert "denied" in r.error.lower()

@pytest.mark.asyncio
async def test_write_outside_workspace_denied(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.write_file("../evil.txt", "x")
    assert not r.success
    assert "denied" in r.error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_sandbox.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/sandbox.py`:
```python
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from sentinel.core.types import ToolResult


class InProcessSandbox:
    """Restricted working-directory sandbox (no container isolation)."""

    def __init__(self, workspace: str) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        p = (self.workspace / path).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise PermissionError(f"path outside workspace denied: {path}")
        return p

    async def run(self, command: list[str], cwd: str | None = None) -> ToolResult:
        try:
            proc = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return ToolResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    async def read_file(self, path: str) -> ToolResult:
        try:
            p = self._resolve(path)
            return ToolResult(success=True, stdout=p.read_text(encoding="utf-8"))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    async def write_file(self, path: str, content: str) -> ToolResult:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_sandbox.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/sandbox.py tests/test_sandbox.py
git commit -m "feat(core): add InProcessSandbox with path boundary enforcement"
```

---

