"""Turn a raw ChangeItem into a publish-ready ProcessedItem via an LLM."""

from __future__ import annotations

import json
import logging

from m365_confluence.ai.base import AIProvider
from m365_confluence.ai.prompts import build_system_prompt, build_user_prompt, parse_response
from m365_confluence.models import ChangeItem, ProcessedItem

log = logging.getLogger("m365_confluence")

_REPAIR_SYSTEM = (
    "You fix malformed JSON. Return ONLY the corrected, valid JSON object "
    "(RFC 8259) with no commentary and no markdown fences. Preserve the "
    "content; only fix the JSON syntax (escape inner quotes, remove trailing "
    "commas, close brackets)."
)


def process_item(provider: AIProvider, item: ChangeItem, language: str = "de") -> ProcessedItem:
    system = build_system_prompt(language)
    prompt = build_user_prompt(item)
    raw = provider.complete(system, prompt)
    try:
        return parse_response(raw, item)
    except (json.JSONDecodeError, ValueError):
        log.warning("Invalid JSON for %s, attempting repair", item.dedupe_key())
        repaired = provider.complete(_REPAIR_SYSTEM, raw)
        return parse_response(repaired, item)
