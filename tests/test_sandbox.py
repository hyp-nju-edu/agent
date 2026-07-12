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
