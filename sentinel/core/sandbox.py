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

    async def list_dir(self, path: str = ".") -> ToolResult:
        try:
            p = self._resolve(path)
            if not p.is_dir():
                return ToolResult(success=False, error=f"not a directory: {path}")
            entries = sorted(
                (f.name + "/" if f.is_dir() else f.name) for f in p.iterdir()
            )
            return ToolResult(success=True, stdout="\n".join(entries))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    async def search(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            import re
            base = self._resolve(path)
            regex = re.compile(pattern)
            matches: list[str] = []
            for f in sorted(base.rglob("*.py")):
                try:
                    for i, line in enumerate(
                        f.read_text(encoding="utf-8").splitlines(), 1
                    ):
                        if regex.search(line):
                            matches.append(f"{f.relative_to(base)}:{i}: {line.strip()}")
                except Exception:
                    continue
            return ToolResult(success=True, stdout="\n".join(matches))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
