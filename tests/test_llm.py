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
