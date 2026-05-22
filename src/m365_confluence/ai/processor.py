"""Turn a raw ChangeItem into a publish-ready ProcessedItem via an LLM."""

from __future__ import annotations

from m365_confluence.ai.base import AIProvider
from m365_confluence.ai.prompts import build_system_prompt, build_user_prompt, parse_response
from m365_confluence.models import ChangeItem, ProcessedItem


def process_item(provider: AIProvider, item: ChangeItem, language: str = "de") -> ProcessedItem:
    system = build_system_prompt(language)
    prompt = build_user_prompt(item)
    raw = provider.complete(system, prompt)
    return parse_response(raw, item)
