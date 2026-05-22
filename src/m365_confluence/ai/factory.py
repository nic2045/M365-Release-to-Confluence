"""Build an AIProvider from configuration."""

from __future__ import annotations

from m365_confluence.ai.base import AIProvider
from m365_confluence.ai.providers import AnthropicProvider, OpenAICompatibleProvider
from m365_confluence.config import AIConfig, ConfigError


def build_provider(config: AIConfig) -> AIProvider:
    if config.provider == "anthropic":
        if not config.anthropic_api_key:
            raise ConfigError("ANTHROPIC_API_KEY is required for AI_PROVIDER=anthropic")
        return AnthropicProvider(config.anthropic_api_key, config.anthropic_model)

    if config.provider == "azure_openai":
        if not (config.azure_endpoint and config.azure_api_key and config.azure_deployment):
            raise ConfigError(
                "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_DEPLOYMENT "
                "are required for AI_PROVIDER=azure_openai"
            )
        return OpenAICompatibleProvider.for_azure(
            config.azure_endpoint,
            config.azure_api_key,
            config.azure_deployment,
            config.azure_api_version,
        )

    if config.provider == "local":
        if not config.local_model:
            raise ConfigError("LOCAL_LLM_MODEL is required for AI_PROVIDER=local")
        return OpenAICompatibleProvider.for_local(
            config.local_base_url,
            config.local_api_key,
            config.local_model,
        )

    raise ConfigError(f"Unsupported AI provider: {config.provider}")
