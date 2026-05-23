"""Turn a raw ChangeItem into a publish-ready ProcessedItem via an LLM."""

from __future__ import annotations

import json
import logging

from m365_confluence.ai.base import AIProvider
from m365_confluence.ai.prompts import (
    build_system_prompt,
    build_user_prompt,
    parse_response,
    render_storage,
)
from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.quarters import derive_quarter, quarter_from_date

log = logging.getLogger("m365_confluence")

_REPAIR_SYSTEM = (
    "You fix malformed JSON. Return ONLY the corrected, valid JSON object "
    "(RFC 8259) with no commentary and no markdown fences. Preserve the "
    "content; only fix the JSON syntax (escape inner quotes, remove trailing "
    "commas, close brackets)."
)


def process_item(
    provider: AIProvider,
    item: ChangeItem,
    language: str = "de",
    org_context: str = "",
) -> ProcessedItem:
    system = build_system_prompt(language, org_context)
    hint = derive_quarter(item)
    prompt = build_user_prompt(item, hint)
    raw = provider.complete(system, prompt)
    try:
        processed = parse_response(raw, item)
    except (json.JSONDecodeError, ValueError):
        log.warning("Invalid JSON for %s, attempting repair", item.dedupe_key())
        repaired = provider.complete(_REPAIR_SYSTEM, raw)
        processed = parse_response(repaired, item)

    # MS-provided release date is authoritative; otherwise fall back to the hint.
    ms_quarter = quarter_from_date(item.release_date) if item.release_date else ""
    final_quarter = ms_quarter or processed.target_quarter or hint
    if final_quarter != processed.target_quarter:
        processed.target_quarter = final_quarter
        processed.confluence_body = render_storage(processed)
    return processed
