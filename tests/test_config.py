import pytest

from m365_confluence.config import ConfigError, ConfluenceConfig


def _base_env(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://confluence.example.com/")
    monkeypatch.setenv("CONFLUENCE_SPACE", "OPS")
    monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
    monkeypatch.delenv("ConfluencePAT", raising=False)


def test_token_from_confluence_token(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("CONFLUENCE_TOKEN", "tok-a")
    assert ConfluenceConfig.from_env().token == "tok-a"


def test_token_falls_back_to_confluence_pat(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("ConfluencePAT", "tok-b")
    cfg = ConfluenceConfig.from_env()
    assert cfg.token == "tok-b"
    assert cfg.base_url == "https://confluence.example.com"  # trailing slash stripped


def test_confluence_token_wins_over_pat(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("CONFLUENCE_TOKEN", "tok-a")
    monkeypatch.setenv("ConfluencePAT", "tok-b")
    assert ConfluenceConfig.from_env().token == "tok-a"


def test_missing_token_raises(monkeypatch):
    _base_env(monkeypatch)
    with pytest.raises(ConfigError):
        ConfluenceConfig.from_env()


def test_filter_config_from_env(monkeypatch):
    from m365_confluence.config import FilterConfig

    monkeypatch.setenv("FILTER_PRODUCTS", "Teams, Exchange ,")
    monkeypatch.setenv("FILTER_MAJOR_ONLY", "true")
    monkeypatch.setenv("FILTER_QUARTER", "Q3 2026")
    monkeypatch.delenv("FILTER_CATEGORIES", raising=False)
    monkeypatch.delenv("FILTER_ACTION_REQUIRED", raising=False)

    f = FilterConfig.from_env()
    assert f.products == ["Teams", "Exchange"]
    assert f.major_only is True
    assert f.action_required is False
    assert f.quarter == "Q3 2026"
    assert f.categories == []
