# Task 15: Config Loader — Report

## What I Implemented

Created three files per the task brief:

1. **`sentinel/core/config.py`** — `Config` dataclass and `load_config(path) -> Config` function.
   - `Config` fields: `provider`, `model` (required, no default), `max_turns` (default 10), `approval_timeout` (default 30), `sandbox` (dict, default `{"image": "sentinel-sandbox:latest", "network": False}`), `tools` (list, default `[]`), `guardrail_patterns` (list, default `[]`).
   - `load_config` reads YAML via `yaml.safe_load`, coerces empty file to `{}`, computes `REQUIRED - set(data.keys())` and raises `ValueError(f"missing required config keys: ...")` if any required keys are absent, then constructs the `Config`.
   - Required keys: `{"provider", "model"}`.
   - No secret fields on the dataclass — secrets live in the keyring, not config (per global constraints).

2. **`sentinel.yaml`** — default repo config with provider=openai, model=gpt-4o-mini, max_turns=10, approval_timeout=30, sandbox image/network, 6 tools, and 3 guardrail patterns (`rm -rf`, `DROP TABLE`, `git push --force`).

3. **`tests/test_config.py`** — two tests verbatim from the brief:
   - `test_load_config` — loads a full YAML and asserts every field.
   - `test_load_config_missing_required_raises` — YAML with only `provider` raises `ValueError` matching `"missing"`.

## TDD Evidence

**RED** (Step 2, before implementation):
```
ModuleNotFoundError: No module named 'sentinel.core.config'
ERROR tests/test_config.py
1 error during collection
```

**GREEN** (Step 4, after implementation):
```
tests/test_config.py::test_load_config PASSED                            [ 50%]
tests/test_config.py::test_load_config_missing_required_raises PASSED    [100%]
2 passed in 0.11s
```

**Full suite** (no regressions): `85 passed in 0.47s`

## Files Changed

- `sentinel/core/config.py` (new, 35 lines)
- `sentinel.yaml` (new, 11 lines)
- `tests/test_config.py` (new, 33 lines)

## Commit

`a4e0d9e feat(config): add YAML config loader with required-key validation`

## Self-Review Findings

- Implementation matches the brief verbatim — no deviations.
- `Config` dataclass fields exactly match the global-constraint spec (provider, model, max_turns, approval_timeout, sandbox dict, tools list, guardrail_patterns list).
- Required-key validation raises `ValueError` whose message contains "missing" (satisfies `pytest.raises(ValueError, match="missing")`).
- Empty/None YAML is coerced to `{}` via `or {}`, so an empty config file raises the missing-key error rather than a TypeError — robust.
- `from __future__ import annotations` is present, matching the codebase style (see `sentinel/core/guardrails.py`).
- No secrets in config: the dataclass has no API-key/token fields; provider and model are non-secret routing metadata.
- Conventional Commit message follows repo style (`feat(scope): ...`).
- Git CRLF warnings on Windows are cosmetic only; files committed with LF in repo.

## Concerns

- **Minor (non-blocking):** the default `sandbox` dict literal is duplicated in three places (dataclass default, `load_config` fallback). This is per the brief's exact code; a future refactor could extract a `DEFAULT_SANDBOX` constant, but I kept the brief's verbatim form to avoid scope creep.
- **Minor (non-blocking):** no runtime type validation of YAML values (e.g., a string `max_turns: "8"` would be accepted). The brief does not require this and no test exercises it; left as-is for now.
- No blocking concerns. Task complete.
