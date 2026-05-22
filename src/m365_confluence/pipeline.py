"""Orchestrate: fetch -> aggregate -> AI process -> publish to Confluence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from m365_confluence.ai import build_provider, process_item
from m365_confluence.ai.prompts import render_storage
from m365_confluence.config import Config
from m365_confluence.confluence import ConfluenceClient
from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.quarters import derive_quarter, quarter_key
from m365_confluence.reporting import build_dashboard_body, dashboard_title, group_by_quarter
from m365_confluence.sources import MessageCenterSource, RoadmapSource, aggregate
from m365_confluence.state import StateStore

log = logging.getLogger("m365_confluence")


@dataclass
class RunResult:
    fetched: int
    processed: int
    published: int
    skipped: int
    unchanged: int
    slipped: int
    dashboards: int
    titles: list[str] = field(default_factory=list)


def collect(config: Config) -> list[list[ChangeItem]]:
    item_lists: list[list[ChangeItem]] = []
    if config.graph is not None:
        log.info("Fetching Message Center messages...")
        item_lists.append(MessageCenterSource(config.graph).fetch())
    if config.roadmap is not None:
        log.info("Fetching M365 roadmap...")
        item_lists.append(RoadmapSource(config.roadmap).fetch())
    return item_lists


def _detect_slip(result: ProcessedItem, previous_quarter: str) -> None:
    if not (previous_quarter and result.target_quarter):
        return
    if quarter_key(result.target_quarter) > quarter_key(previous_quarter):
        result.slipped = True
        result.previous_quarter = previous_quarter
        result.confluence_body = render_storage(result)


def run(
    config: Config,
    *,
    since_days: int | None = None,
    limit: int | None = None,
    quarter: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    title_prefix: str = "[M365] ",
    state_file: str = "m365_state.json",
) -> RunResult:
    since = None
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    items = aggregate(collect(config), since=since, limit=limit)
    if quarter:
        items = [i for i in items if derive_quarter(i) == quarter]
    log.info("Aggregated %d change item(s)", len(items))

    state = StateStore(state_file).load()
    provider = build_provider(config.ai)
    confluence = None if dry_run else ConfluenceClient(config.confluence)

    processed: list[ProcessedItem] = []
    published = 0
    skipped = 0
    unchanged = 0
    slipped = 0
    total = len(items)
    for index, item in enumerate(items, start=1):
        key = item.dedupe_key()
        if not force and state.is_unchanged(item):
            log.info("[%d/%d] Unchanged, skipping %s", index, total, key)
            state.touch(key)
            unchanged += 1
            continue

        log.info("[%d/%d] Processing %s ...", index, total, key)
        started = time.monotonic()
        try:
            result = process_item(provider, item, config.ai.output_language, config.ai.org_context)
        except Exception:
            log.exception("[%d/%d] Skipping %s: processing failed", index, total, key)
            skipped += 1
            continue

        previous = state.get(key)
        _detect_slip(result, previous.target_quarter if previous else "")
        if result.slipped:
            slipped += 1
            log.warning(
                "[%d/%d] Slip: %s moved %s -> %s",
                index,
                total,
                key,
                result.previous_quarter,
                result.target_quarter,
            )

        log.info(
            "[%d/%d] Summarised %s in %.1fs (quarter=%s, decision=%s)",
            index,
            total,
            key,
            time.monotonic() - started,
            result.target_quarter or "?",
            result.decision or "?",
        )
        result.confluence_title = f"{title_prefix}{result.confluence_title}"
        processed.append(result)

        if confluence is not None:
            try:
                confluence.upsert_page(result.confluence_title, result.confluence_body)
                published += 1
                log.info("[%d/%d] Published: %s", index, total, result.confluence_title)
            except Exception:
                log.exception("[%d/%d] Skipping %s: Confluence write failed", index, total, key)
                skipped += 1
                continue

        state.record(item, result)

    dashboards = _publish_dashboards(state, confluence, title_prefix, dry_run)

    if not dry_run:
        state.save()
        log.info("State saved to %s", state_file)

    return RunResult(
        fetched=len(items),
        processed=len(processed),
        published=published,
        skipped=skipped,
        unchanged=unchanged,
        slipped=slipped,
        dashboards=dashboards,
        titles=[p.confluence_title for p in processed],
    )


def _publish_dashboards(state, confluence, title_prefix: str, dry_run: bool) -> int:
    groups = group_by_quarter(state.all_items())
    count = 0
    for quarter_label, items in groups.items():
        title = dashboard_title(quarter_label, title_prefix)
        body = build_dashboard_body(quarter_label, items)
        if dry_run or confluence is None:
            log.info("Dashboard (dry-run): %s (%d items)", title, len(items))
            count += 1
            continue
        try:
            confluence.upsert_page(title, body)
            log.info("Dashboard published: %s (%d items)", title, len(items))
            count += 1
        except Exception:
            log.exception("Dashboard write failed: %s", title)
    return count
