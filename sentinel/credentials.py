from __future__ import annotations
from typing import Any, Protocol


class KeyringBackend(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def get_password(self, service: str, username: str) -> str | None: ...
    def delete_password(self, service: str, username: str) -> None: ...


SERVICE_NAME = "sentinel"
PROVIDERS = ["openai", "anthropic"]


class CredentialStore:
    """OS keyring-backed credential store. Keys never logged or echoed."""

    def __init__(self, backend: KeyringBackend | None = None) -> None:
        if backend is not None:
            self._backend = backend
        else:
            import keyring
            self._backend = keyring

    def set_key(self, provider: str, key: str) -> None:
        self._backend.set_password(SERVICE_NAME, provider, key)

    def get_key(self, provider: str) -> str | None:
        return self._backend.get_password(SERVICE_NAME, provider)

    def clear_key(self, provider: str) -> None:
        try:
            self._backend.delete_password(SERVICE_NAME, provider)
        except Exception:
            pass

    def status(self) -> dict[str, str]:
        return {p: ("set" if self.get_key(p) else "not set") for p in PROVIDERS}
