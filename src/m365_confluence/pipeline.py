"""Orchestrate: fetch -> aggregate -> AI process -> publish to Confluence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from m365_confluence.ai import build_provider, process_item
from m365_confluence.config import Config
from m365_confluence.confluence import ConfluenceClient
from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.sources import MessageCenterSource, RoadmapSource, aggregate

log = logging.getLogger("m365_confluence")


@dataclass
class RunResult:
    fetched: int
    processed: int
    published: int
    skipped: int
    titles: list[str]


def collect(config: Config) -> list[list[ChangeItem]]:
    item_lists: list[list[ChangeItem]] = []
    if config.graph is not None:
        log.info("Fetching Message Center messages...")
        item_lists.append(MessageCenterSource(config.graph).fetch())
    if config.roadmap is not None:
        log.info("Fetching M365 roadmap...")
        item_lists.append(RoadmapSource(config.roadmap).fetch())
    return item_lists


def run(
    config: Config,
    *,
    since_days: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    title_prefix: str = "[M365] ",
) -> RunResult:
    since = None
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    items = aggregate(collect(config), since=since, limit=limit)
    log.info("Aggregated %d change item(s)", len(items))

    provider = build_provider(config.ai)
    confluence = None if dry_run else ConfluenceClient(config.confluence)

    processed: list[ProcessedItem] = []
    published = 0
    skipped = 0
    total = len(items)
    for index, item in enumerate(items, start=1):
        log.info("[%d/%d] Processing %s ...", index, total, item.dedupe_key())
        started = time.monotonic()
        try:
            result = process_item(provider, item, config.ai.output_language)
        except Exception:
            log.exception("[%d/%d] Skipping %s: processing failed", index, total, item.dedupe_key())
            skipped += 1
            continue
        log.info(
            "[%d/%d] Summarised %s in %.1fs",
            index,
            total,
            item.dedupe_key(),
            time.monotonic() - started,
        )
        result.confluence_title = f"{title_prefix}{result.confluence_title}"
        processed.append(result)
        if confluence is not None:
            try:
                confluence.upsert_page(result.confluence_title, result.confluence_body)
                published += 1
                log.info("[%d/%d] Published: %s", index, total, result.confluence_title)
            except Exception:
                log.exception(
                    "[%d/%d] Skipping %s: Confluence write failed",
                    index,
                    total,
                    item.dedupe_key(),
                )
                skipped += 1

    return RunResult(
        fetched=len(items),
        processed=len(processed),
        published=published,
        skipped=skipped,
        titles=[p.confluence_title for p in processed],
    )
