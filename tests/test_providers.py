import json
import pytest
import httpx
from sentinel.core.providers import OpenAIProvider, AnthropicProvider


def _openai_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "gpt-4o-mini"
    assert request.headers["authorization"] == "Bearer sk-test"
    return httpx.Response(200, json={
        "choices": [{
            "message": {
                "content": "I will run pytest",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "run_shell",
                                  "arguments": "{\"cmd\": \"pytest\"}"},
                }],
            }
        }]
    })


def _openai_text_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": "done", "tool_calls": []}}]
    })


@pytest.mark.asyncio
async def test_openai_provider_parses_text_and_tool_calls():
    transport = httpx.MockTransport(_openai_handler)
    client = httpx.AsyncClient(transport=transport,
                               base_url="https://api.openai.com")
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
    resp = await p.complete(
        messages=[{"role": "user", "content": "go"}], tools=["run_shell"])
    assert resp.text == "I will run pytest"
    assert resp.tool_calls == [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_text_only():
    transport = httpx.MockTransport(_openai_text_handler)
    client = httpx.AsyncClient(transport=transport,
                               base_url="https://api.openai.com")
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
    resp = await p.complete(messages=[], tools=[])
    assert resp.text == "done"
    assert resp.tool_calls == []
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_raises_on_http_error():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "bad key"}})
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport,
                               base_url="https://api.openai.com")
    p = OpenAIProvider(api_key="sk-bad", model="gpt-4o-mini", client=client)
    with pytest.raises(RuntimeError, match="openai api error"):
        await p.complete(messages=[], tools=[])
    await client.aclose()


def _anthropic_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "claude-sonnet-4-20250514"
    assert request.headers["x-api-key"] == "sk-ant-test"
    return httpx.Response(200, json={
        "content": [
            {"type": "text", "text": "running tests"},
            {"type": "tool_use", "id": "tu_1",
             "name": "run_shell", "input": {"cmd": "pytest"}},
        ]
    })


@pytest.mark.asyncio
async def test_anthropic_provider_parses_text_and_tool_use():
    transport = httpx.MockTransport(_anthropic_handler)
    client = httpx.AsyncClient(transport=transport,
                               base_url="https://api.anthropic.com")
    p = AnthropicProvider(api_key="sk-ant-test",
                          model="claude-sonnet-4-20250514", client=client)
    resp = await p.complete(
        messages=[{"role": "user", "content": "go"}], tools=["run_shell"])
    assert resp.text == "running tests"
    assert resp.tool_calls == [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    await client.aclose()


@pytest.mark.asyncio
async def test_anthropic_provider_text_only():
    def handler(request):
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "all done"}]
        })
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport,
                               base_url="https://api.anthropic.com")
    p = AnthropicProvider(api_key="sk-ant-test",
                          model="claude-sonnet-4-20250514", client=client)
    resp = await p.complete(messages=[], tools=[])
    assert resp.text == "all done"
    assert resp.tool_calls == []
    await client.aclose()
