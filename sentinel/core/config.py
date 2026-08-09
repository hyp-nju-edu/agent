from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    provider: str
    model: str
    max_turns: int = 10
    approval_timeout: int = 30
    api_base: dict[str, str] = field(default_factory=dict)
    sandbox: dict = field(default_factory=lambda: {"image": "sentinel-sandbox:latest", "network": False})
    tools: list[str] = field(default_factory=list)
    guardrail_patterns: list[str] = field(default_factory=list)


REQUIRED = {"provider", "model"}


def load_config(path: str) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = REQUIRED - set(data.keys())
    if missing:
        raise ValueError(f"missing required config keys: {sorted(missing)}")
    return Config(
        provider=data["provider"],
        model=data["model"],
        max_turns=data.get("max_turns", 10),
        approval_timeout=data.get("approval_timeout", 30),
        api_base=data.get("api_base", {}),
        sandbox=data.get("sandbox", {"image": "sentinel-sandbox:latest", "network": False}),
        tools=data.get("tools", []),
        guardrail_patterns=data.get("guardrail_patterns", []),
    )
