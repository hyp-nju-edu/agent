import pytest
from fastapi.testclient import TestClient

from sentinel.server.app import create_app


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
