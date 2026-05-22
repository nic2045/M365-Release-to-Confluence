"""LLM provider protocol."""

from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    """A minimal text-completion interface implemented by every backend."""

    def complete(self, system: str, prompt: str) -> str:
        """Return the model's text response for the given system + user prompt."""
        ...
