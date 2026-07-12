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
