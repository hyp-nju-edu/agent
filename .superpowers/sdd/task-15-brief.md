## Task 15: Config Loader

**Files:**
- Create: `sentinel/core/config.py`
- Create: `sentinel.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass, `load_config(path) -> Config`. Reads provider/model, allowed tools, risk thresholds, sandbox, guardrail patterns, max_turns, approval timeout.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import textwrap
from sentinel.core.config import load_config, Config

def test_load_config(tmp_path):
    yaml = textwrap.dedent("""
        provider: openai
        model: gpt-4o-mini
        max_turns: 8
        approval_timeout: 30
        sandbox:
          image: sentinel-sandbox:latest
          network: false
        tools: [read_file, write_file, run_shell, run_tests]
        guardrail_patterns: ["rm -rf", "DROP TABLE"]
    """)
    p = tmp_path / "sentinel.yaml"
    p.write_text(yaml)
    cfg = load_config(str(p))
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.max_turns == 8
    assert cfg.approval_timeout == 30
    assert cfg.sandbox["network"] is False
    assert "run_shell" in cfg.tools
    assert "rm -rf" in cfg.guardrail_patterns

def test_load_config_missing_required_raises(tmp_path):
    import pytest
    p = tmp_path / "bad.yaml"
    p.write_text("provider: openai\n")
    with pytest.raises(ValueError, match="missing"):
        load_config(str(p))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/config.py`:
```python
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
        sandbox=data.get("sandbox", {"image": "sentinel-sandbox:latest", "network": False}),
        tools=data.get("tools", []),
        guardrail_patterns=data.get("guardrail_patterns", []),
    )
```

`sentinel.yaml`:
```yaml
provider: openai
model: gpt-4o-mini
max_turns: 10
approval_timeout: 30
sandbox:
  image: sentinel-sandbox:latest
  network: false
tools: [read_file, write_file, list_dir, run_shell, run_tests, search]
guardrail_patterns:
  - "rm -rf"
  - "DROP TABLE"
  - "git push --force"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_config.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/config.py sentinel.yaml tests/test_config.py
git commit -m "feat(config): add YAML config loader with required-key validation"
```

---

