"""Concrete LLM provider implementations.

Three backends are supported:

* ``AnthropicProvider`` — Claude via the Anthropic SDK (with prompt caching).
* ``OpenAICompatibleProvider`` — any OpenAI-compatible Chat Completions API.
  This covers both Azure OpenAI and a local LLM (Ollama, LM Studio, vLLM, ...).

SDKs are imported lazily so importing this module never requires every SDK
to be installed.
"""

from __future__ import annotations

_MAX_TOKENS = 4096


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text")


class OpenAICompatibleProvider:
    """Works against Azure OpenAI and any local OpenAI-compatible endpoint."""

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def for_azure(
        cls, endpoint: str, api_key: str, deployment: str, api_version: str
    ) -> OpenAICompatibleProvider:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        # For Azure the deployment name is used as the model identifier.
        return cls(client, deployment)

    @classmethod
    def for_local(cls, base_url: str, api_key: str, model: str) -> OpenAICompatibleProvider:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        return cls(client, model)

    def complete(self, system: str, prompt: str) -> str:
        completion = self._client.chat.completions.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content or ""
