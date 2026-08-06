import getpass

import pytest
from fastapi.testclient import TestClient

from sentinel.credentials import CredentialStore
from sentinel.core.config import Config


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_config_status(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-x")
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    main(["config", "status"])
    out = capsys.readouterr().out
    assert "openai: set" in out
    assert "anthropic: not set" in out


def test_config_set_key(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")
    main(["config", "set-key", "--provider", "openai"])
    assert cs.get_key("openai") == "sk-secret"
    out = capsys.readouterr().out
    assert "sk-secret" not in out


def test_config_clear_key(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("anthropic", "sk-ant-x")
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    main(["config", "clear-key", "--provider", "anthropic"])
    assert cs.get_key("anthropic") is None


def test_build_server_app_defaults():
    from sentinel.cli import build_server_app
    kr = FakeKeyring()
    kr.set_password("sentinel", "openai", "sk-x")
    cs = CredentialStore(backend=kr)
    app = build_server_app(Config(provider="openai", model="gpt-4o-mini"), cs)
    data = TestClient(app).get("/models").json()
    assert data["default"] == {"provider": "openai", "model": "gpt-4o-mini"}


def test_build_server_app_missing_key_raises():
    from sentinel.cli import build_server_app
    cs = CredentialStore(backend=FakeKeyring())
    with pytest.raises(RuntimeError, match="no api key"):
        build_server_app(Config(provider="openai", model="gpt-4o-mini"), cs)
