from sentinel.credentials import CredentialStore


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_set_and_get_key():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-abc123")
    assert cs.get_key("openai") == "sk-abc123"


def test_get_key_missing_returns_none():
    cs = CredentialStore(backend=FakeKeyring())
    assert cs.get_key("openai") is None


def test_clear_key():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("anthropic", "sk-ant-x")
    cs.clear_key("anthropic")
    assert cs.get_key("anthropic") is None


def test_clear_key_missing_no_error():
    cs = CredentialStore(backend=FakeKeyring())
    cs.clear_key("openai")


def test_status_shows_set_and_not_set():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-x")
    s = cs.status()
    assert s["openai"] == "set"
    assert s["anthropic"] == "not set"


def test_status_never_shows_plaintext():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-super-secret-12345")
    s = str(cs.status())
    assert "sk-super-secret" not in s
