import os
import pytest
from sentinel.core.config import Config
from sentinel.core.providers import OpenAIProvider, AnthropicProvider
from sentinel.credentials import CredentialStore
from sentinel.server.app import build_llm


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_build_llm_openai():
    cs = CredentialStore(backend=FakeKeyring())
    cs.set_key("openai", "sk-test")
    config = Config(provider="openai", model="gpt-4o-mini")
    llm = build_llm(config=config, credential_store=cs, env={})
    assert isinstance(llm, OpenAIProvider)


def test_build_llm_anthropic():
    cs = CredentialStore(backend=FakeKeyring())
    cs.set_key("anthropic", "sk-ant-test")
    config = Config(provider="anthropic", model="claude-sonnet-4-20250514")
    llm = build_llm(config=config, credential_store=cs, env={})
    assert isinstance(llm, AnthropicProvider)


def test_build_llm_env_fallback():
    cs = CredentialStore(backend=FakeKeyring())
    config = Config(provider="openai", model="gpt-4o-mini")
    llm = build_llm(config=config, credential_store=cs,
                    env={"OPENAI_API_KEY": "sk-env"})
    assert isinstance(llm, OpenAIProvider)


def test_build_llm_no_key_raises():
    cs = CredentialStore(backend=FakeKeyring())
    config = Config(provider="openai", model="gpt-4o-mini")
    with pytest.raises(RuntimeError, match="no api key"):
        build_llm(config=config, credential_store=cs, env={})


def test_build_llm_unknown_provider_raises():
    cs = CredentialStore(backend=FakeKeyring())
    cs.set_key("unknown", "sk-x")
    config = Config(provider="unknown", model="x")
    with pytest.raises(ValueError, match="unknown provider"):
        build_llm(config=config, credential_store=cs, env={})


def test_build_llm_passes_base_url_openai():
    cs = CredentialStore(backend=FakeKeyring())
    cs.set_key("openai", "sk-test")
    config = Config(provider="openai", model="gpt-4o-mini",
                    api_base={"openai": "https://proxy.example.com"})
    llm = build_llm(config=config, credential_store=cs, env={})
    assert llm._base_url == "https://proxy.example.com"


def test_build_llm_default_base_url_openai():
    cs = CredentialStore(backend=FakeKeyring())
    cs.set_key("openai", "sk-test")
    config = Config(provider="openai", model="gpt-4o-mini")
    llm = build_llm(config=config, credential_store=cs, env={})
    assert llm._base_url == "https://api.openai.com"
