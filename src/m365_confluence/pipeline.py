"""Orchestrate: fetch -> aggregate -> AI process -> publish to Confluence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from m365_confluence.ai import build_provider, process_item
from m365_confluence.config import Config
from m365_confluence.confluence import ConfluenceClient
from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.sources import MessageCenterSource, RoadmapSource, aggregate

log = logging.getLogger("m365_confluence")


@dataclass(slots=True)
class RunResult:
    fetched: int
    processed: int
    published: int
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
    for item in items:
        log.info("Processing %s", item.dedupe_key())
        result = process_item(provider, item, config.ai.output_language)
        result.confluence_title = f"{title_prefix}{result.confluence_title}"
        processed.append(result)
        if confluence is not None:
            confluence.upsert_page(result.confluence_title, result.confluence_body)
            published += 1

    return RunResult(
        fetched=len(items),
        processed=len(processed),
        published=published,
        titles=[p.confluence_title for p in processed],
    )
