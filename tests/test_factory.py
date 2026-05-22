import pytest

from m365_confluence.ai.factory import build_provider
from m365_confluence.config import AIConfig, ConfigError


def test_anthropic_requires_key():
    with pytest.raises(ConfigError):
        build_provider(AIConfig(provider="anthropic", anthropic_api_key=""))


def test_azure_requires_settings():
    with pytest.raises(ConfigError):
        build_provider(AIConfig(provider="azure_openai"))


def test_local_requires_model():
    with pytest.raises(ConfigError):
        build_provider(AIConfig(provider="local", local_model=""))
