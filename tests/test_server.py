import pytest
from fastapi.testclient import TestClient

from sentinel.server.app import MODEL_REGISTRY, create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_websocket_streams_events():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        events = []
        for _ in range(20):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    types = [e["type"] for e in events]
    assert "TurnStarted" in types
    assert "Stopped" in types


def test_websocket_streams_action_executed():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        events = []
        for _ in range(20):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    assert any(e["type"] == "ActionExecuted" for e in events)


def test_audit_endpoint():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        for _ in range(20):
            msg = ws.receive_json()
            if msg.get("type") == "Stopped":
                break
    r = client.get("/audit")
    assert r.status_code == 200
    entries = r.json()
    assert isinstance(entries, list)
    assert len(entries) > 0


def test_models_endpoint_defaults():
    client = TestClient(create_app())
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert set(data["providers"]) == {"openai", "anthropic"}
    assert data["providers"]["openai"] == [
        "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"]
    assert data["default"] == {"provider": "openai", "model": "gpt-4o-mini"}


def test_models_endpoint_custom_defaults():
    client = TestClient(create_app(
        default_provider="anthropic", default_model="claude-sonnet-4"))
    data = client.get("/models").json()
    assert data["default"] == {"provider": "anthropic", "model": "claude-sonnet-4"}


from sentinel.core.llm import MockLLM, LLMResponse


def test_ws_uses_llm_builder():
    calls = []
    def builder(provider, model):
        calls.append((provider, model))
        return MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    client = TestClient(create_app(llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi", "provider": "anthropic",
                      "model": "claude-sonnet-4"})
        events = []
        for _ in range(10):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "SessionComplete":
                break
    assert calls == [("anthropic", "claude-sonnet-4")]
    assert any(e["type"] == "TurnStarted" for e in events)


def test_ws_llm_builder_error_sends_error_event():
    def builder(provider, model):
        raise RuntimeError(f"no api key for provider '{provider}'")
    client = TestClient(create_app(llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi", "provider": "openai",
                      "model": "gpt-4o-mini"})
        events = []
        for _ in range(5):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "SessionComplete":
                break
    types = [e["type"] for e in events]
    assert "Error" in types
    assert types[-1] == "SessionComplete"
    assert "TurnStarted" not in types


def test_ws_without_provider_falls_back_to_injected_llm():
    calls = []
    def builder(provider, model):
        calls.append((provider, model))
        return MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    injected = MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    client = TestClient(create_app(llm=injected, llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi"})
        events = []
        for _ in range(10):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    assert calls == []
    assert any(e["type"] == "TurnStarted" for e in events)
