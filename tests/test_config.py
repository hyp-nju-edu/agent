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

def test_load_config_api_base(tmp_path):
    import textwrap
    yaml = textwrap.dedent("""
        provider: openai
        model: gpt-4o-mini
        api_base:
          openai: https://proxy.example.com
          anthropic: https://proxy-anthropic.example.com
    """)
    p = tmp_path / "sentinel.yaml"
    p.write_text(yaml)
    cfg = load_config(str(p))
    assert cfg.api_base["openai"] == "https://proxy.example.com"
    assert cfg.api_base["anthropic"] == "https://proxy-anthropic.example.com"

def test_config_api_base_defaults_empty():
    assert Config(provider="openai", model="m").api_base == {}
