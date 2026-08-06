from __future__ import annotations
import shlex
from typing import Any

from sentinel.core.types import RiskLevel, ToolResult
from sentinel.core.tools import SandboxBackend, Tool


class ReadFileTool:
    name = "read_file"
    risk_level = RiskLevel.LOW

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        path = args.get("path", "")
        return await sandbox.read_file(path)


class WriteFileTool:
    name = "write_file"
    risk_level = RiskLevel.MEDIUM

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        path = args.get("path", "")
        content = args.get("content", "")
        return await sandbox.write_file(path, content)


class ListDirTool:
    name = "list_dir"
    risk_level = RiskLevel.LOW

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        path = args.get("path", ".")
        return await sandbox.list_dir(path)


class RunShellTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        cmd = args.get("cmd", "")
        command = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        return await sandbox.run(command)


class RunTestsTool:
    name = "run_tests"
    risk_level = RiskLevel.MEDIUM

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        extra = args.get("args", [])
        if isinstance(extra, str):
            extra = shlex.split(extra)
        return await sandbox.run(["python", "-m", "pytest", *extra])


class SearchTool:
    name = "search"
    risk_level = RiskLevel.LOW

    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult:
        pattern = args.get("pattern", "")
        path = args.get("path", ".")
        return await sandbox.search(pattern, path)


def default_tools() -> list[Tool]:
    return [
        ReadFileTool(),
        WriteFileTool(),
        ListDirTool(),
        RunShellTool(),
        RunTestsTool(),
        SearchTool(),
    ]
