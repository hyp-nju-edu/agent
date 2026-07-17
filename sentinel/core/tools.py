from __future__ import annotations
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, RiskLevel, ToolResult


class SandboxBackend(Protocol):
    async def run(self, command: list[str], cwd: str | None = None) -> ToolResult: ...
    async def read_file(self, path: str) -> ToolResult: ...
    async def write_file(self, path: str, content: str) -> ToolResult: ...
    async def list_dir(self, path: str = ".") -> ToolResult: ...
    async def search(self, pattern: str, path: str = ".") -> ToolResult: ...


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
