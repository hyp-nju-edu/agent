import pytest
from sentinel.core.types import RiskLevel, ToolResult
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.builtins import (
    ReadFileTool, WriteFileTool, ListDirTool, RunShellTool,
    RunTestsTool, SearchTool, default_tools,
)


@pytest.mark.asyncio
async def test_read_file_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    await sb.write_file("hello.py", "print('hi')")
    t = ReadFileTool()
    r = await t.execute({"path": "hello.py"}, sb)
    assert r.success
    assert "print('hi')" in r.stdout
    assert t.name == "read_file"
    assert t.risk_level == RiskLevel.LOW


@pytest.mark.asyncio
async def test_read_file_missing(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    t = ReadFileTool()
    r = await t.execute({"path": "nope.py"}, sb)
    assert not r.success


@pytest.mark.asyncio
async def test_write_file_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    t = WriteFileTool()
    r = await t.execute({"path": "out/test.py", "content": "x = 1"}, sb)
    assert r.success
    assert t.risk_level == RiskLevel.MEDIUM
    rd = await sb.read_file("out/test.py")
    assert "x = 1" in rd.stdout


@pytest.mark.asyncio
async def test_list_dir_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    await sb.write_file("a.py", "1")
    await sb.write_file("b.py", "2")
    t = ListDirTool()
    r = await t.execute({"path": "."}, sb)
    assert r.success
    assert "a.py" in r.stdout
    assert "b.py" in r.stdout
    assert t.risk_level == RiskLevel.LOW


@pytest.mark.asyncio
async def test_run_shell_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    t = RunShellTool()
    r = await t.execute({"cmd": "python -c \"print('hello')\""}, sb)
    assert r.success
    assert "hello" in r.stdout
    assert t.risk_level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_run_tests_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    t = RunTestsTool()
    r = await t.execute({"args": ["--version"]}, sb)
    assert r.success
    assert t.risk_level == RiskLevel.MEDIUM


@pytest.mark.asyncio
async def test_search_tool(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    await sb.write_file("a.py", "def foo():\n    pass\n")
    await sb.write_file("b.py", "def bar():\n    pass\n")
    t = SearchTool()
    r = await t.execute({"pattern": "def foo", "path": "."}, sb)
    assert r.success
    assert "a.py" in r.stdout
    assert "b.py" not in r.stdout


def test_default_tools_has_all():
    tools = default_tools()
    names = [t.name for t in tools]
    assert "read_file" in names
    assert "write_file" in names
    assert "list_dir" in names
    assert "run_shell" in names
    assert "run_tests" in names
    assert "search" in names
