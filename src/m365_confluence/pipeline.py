"""Orchestrate: fetch -> aggregate -> AI process -> publish to Confluence."""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from m365_confluence.ai import build_provider, process_item
from m365_confluence.ai.prompts import render_storage
from m365_confluence.changelog import ChangelogStore, render_changelog_body
from m365_confluence.config import Config
from m365_confluence.confluence import build_confluence
from m365_confluence.filters import apply_filters, is_rollout_or_live
from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.quarters import derive_quarter, quarter_key
from m365_confluence.reporting import dashboard_title, quarter_dashboards
from m365_confluence.review import draft_from, draft_to, load_drafts, save_drafts
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
    new: int
    changed: int
    dashboards: int
    not_relevant: int = 0
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


def collect_products(config: Config) -> list[tuple[str, int]]:
    """Distinct products across all (deduped) items with their counts, most common first."""
    items = aggregate(collect(config), since=None, limit=None)
    counter: Counter[str] = Counter()
    for item in items:
        for product in item.products:
            if product:
                counter[product] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def _output_relevant(item: ChangeItem, previous) -> bool:
    """Roadmap items count only when newly rollout/live since the last run.

    Message Center posts have no rollout status and are always relevant.
    """
    if item.source != "roadmap":
        return True
    if not is_rollout_or_live(item.status):
        return False
    # Already rollout/live last run -> not new.
    return not (previous is not None and is_rollout_or_live(previous.status))


_FATAL_PROVIDER_MARKERS = (
    "credit balance",
    "plans & billing",
    "authentication_error",
    "invalid x-api-key",
    "invalid api key",
    "incorrect api key",
    "permission_error",
    "insufficient_quota",
)


def _is_fatal_provider_error(exc: Exception) -> bool:
    """True for provider errors that will affect every item (billing/auth/quota)."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _FATAL_PROVIDER_MARKERS)


def _should_make_page(item: ChangeItem, mode: str) -> bool:
    if mode == "all":
        return True
    if mode == "none":
        return False
    return "MajorChange" in item.tags  # mode == "major"


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
    major_only: bool = False,
    action_required: bool = False,
    products: list[str] | None = None,
    categories: list[str] | None = None,
    worldwide_only: bool = False,
    new_rollouts_only: bool = True,
    dry_run: bool = False,
    force: bool = False,
    item_pages: str = "major",
    group_by: str = "service",
    title_prefix: str = "[M365] ",
    state_file: str = "m365_state.json",
    changelog_file: str = "m365_changelog.json",
    review_out: str | None = None,
    confirm_over: int | None = None,
    confirm: Callable[[int, int], bool] | None = None,
) -> RunResult:
    since = None
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    items = aggregate(collect(config), since=since, limit=None)
    if quarter:
        items = [i for i in items if derive_quarter(i) == quarter]
    items = apply_filters(
        items,
        major_only=major_only,
        action_required=action_required,
        products=products,
        categories=categories,
        worldwide_only=worldwide_only,
    )
    if limit is not None:
        items = items[:limit]
    log.info("Aggregated %d change item(s) after filters", len(items))

    state = StateStore(state_file).load()
    provider = build_provider(config.ai)
    need_confluence = not dry_run and not review_out
    confluence = build_confluence(config.confluence) if need_confluence else None

    processed: list[ProcessedItem] = []
    prepared: list[tuple[ChangeItem, ProcessedItem, bool]] = []
    skipped = 0
    unchanged = 0
    not_relevant = 0
    slipped = 0
    new_count = 0
    changed_count = 0

    # Pre-pass: determine which items will actually hit the LLM.
    candidates: list[tuple[ChangeItem, object]] = []
    for item in items:
        previous = state.get(item.dedupe_key())
        if not force and state.is_unchanged(item):
            state.touch(item.dedupe_key())
            unchanged += 1
            continue
        if new_rollouts_only and not _output_relevant(item, previous):
            not_relevant += 1
            continue
        candidates.append((item, previous))

    # Token/cost guard: confirm before sending a large batch to the LLM.
    if (
        candidates
        and confirm is not None
        and confirm_over is not None
        and len(candidates) > confirm_over
    ):
        est_tokens = sum(len(i.body) for i, _ in candidates) // 4
        if not confirm(len(candidates), est_tokens):
            log.warning("Aborted before any LLM call (%d item(s) pending).", len(candidates))
            return RunResult(
                fetched=len(items),
                processed=0,
                published=0,
                skipped=0,
                unchanged=unchanged,
                slipped=0,
                new=0,
                changed=0,
                dashboards=0,
                not_relevant=not_relevant,
                titles=[],
            )

    total = len(candidates)
    for index, (item, previous) in enumerate(candidates, start=1):
        key = item.dedupe_key()
        log.info("[%d/%d] Processing %s ...", index, total, key)
        started = time.monotonic()
        try:
            result = process_item(provider, item, config.ai.output_language, config.ai.org_context)
        except Exception as exc:
            if _is_fatal_provider_error(exc):
                log.error(
                    "Aborting: the AI provider rejected the request — %s. "
                    "Check credits/billing or API key, or switch AI_PROVIDER "
                    "(e.g. 'local' or 'azure_openai').",
                    str(exc).splitlines()[0] if str(exc) else exc,
                )
                break
            log.exception("[%d/%d] Skipping %s: processing failed", index, total, key)
            skipped += 1
            continue

        if previous is None:
            new_count += 1
        else:
            changed_count += 1
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

        make_page = _should_make_page(item, item_pages)
        prepared.append((item, result, make_page))

    if review_out:
        save_drafts(review_out, [draft_from(i, r, mp) for i, r, mp in prepared])
        log.info("Wrote %d draft(s) to %s (nothing published)", len(prepared), review_out)
        return RunResult(
            fetched=len(items),
            processed=len(processed),
            published=0,
            skipped=skipped,
            unchanged=unchanged,
            slipped=slipped,
            new=new_count,
            changed=changed_count,
            dashboards=0,
            not_relevant=not_relevant,
            titles=[r.confluence_title for _, r, _ in prepared],
        )

    published = _publish_prepared(prepared, state, confluence)
    dashboards = _publish_dashboards(state, confluence, title_prefix, dry_run, group_by)
    _update_changelog(
        changelog_file,
        confluence,
        title_prefix,
        dry_run,
        processed=len(processed),
        new=new_count,
        changed=changed_count,
        slipped=slipped,
    )
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
        new=new_count,
        changed=changed_count,
        dashboards=dashboards,
        not_relevant=not_relevant,
        titles=[r.confluence_title for _, r, _ in prepared],
    )


def _publish_prepared(prepared, state, confluence) -> int:
    """Publish per-item pages (when make_page) and record state. Returns published count."""
    published = 0
    total = len(prepared)
    for index, (item, result, make_page) in enumerate(prepared, start=1):
        key = item.dedupe_key()
        previous = state.get(key)
        history = list(previous.quarter_history) if previous else []
        if result.slipped and result.previous_quarter and result.previous_quarter not in history:
            history.append(result.previous_quarter)
        if confluence is not None and make_page:
            try:
                confluence.upsert_page(result.confluence_title, result.confluence_body)
                published += 1
                log.info("[%d/%d] Published: %s", index, total, result.confluence_title)
            except Exception:
                log.exception("[%d/%d] Page write failed: %s", index, total, key)
                continue
        state.record(item, result, has_page=make_page, quarter_history=history)
    return published


def _update_changelog(
    changelog_file: str,
    confluence,
    title_prefix: str,
    dry_run: bool,
    *,
    processed: int,
    new: int,
    changed: int,
    slipped: int,
) -> None:
    if processed == 0:
        log.info("No changes this run; changelog not extended")
        return
    store = ChangelogStore(changelog_file).load()
    entry = store.add(processed=processed, new=new, changed=changed, slipped=slipped)
    log.info("Changelog: %s", entry.summary)
    body = render_changelog_body(store.entries())
    title = f"{title_prefix}Changelog"
    if dry_run or confluence is None:
        log.info("Changelog (dry-run): %s", title)
        return
    try:
        confluence.upsert_page(title, body)
        store.save()
        log.info("Changelog published: %s", title)
    except Exception:
        log.exception("Changelog write failed: %s", title)


def run_from_review(
    config: Config,
    review_file: str,
    *,
    dry_run: bool = False,
    group_by: str = "service",
    title_prefix: str = "[M365] ",
    state_file: str = "m365_state.json",
    changelog_file: str = "m365_changelog.json",
) -> RunResult:
    """Publish edited review drafts to Confluence without calling the LLM."""
    drafts = load_drafts(review_file)
    state = StateStore(state_file).load()
    confluence = None if dry_run else build_confluence(config.confluence)

    prepared: list[tuple[ChangeItem, ProcessedItem, bool]] = []
    new_count = 0
    changed_count = 0
    slipped = 0
    ignored = 0
    for draft in drafts:
        if draft.get("ignored"):
            ignored += 1
            continue
        item, result, make_page = draft_to(draft)
        previous = state.get(item.dedupe_key())
        if previous is None:
            new_count += 1
        else:
            changed_count += 1
        _detect_slip(result, previous.target_quarter if previous else "")
        if not result.confluence_body or result.slipped:
            result.confluence_body = render_storage(result)
        if result.slipped:
            slipped += 1
        prepared.append((item, result, make_page))

    log.info("From review: %d to publish, %d ignored", len(prepared), ignored)
    published = _publish_prepared(prepared, state, confluence)
    dashboards = _publish_dashboards(state, confluence, title_prefix, dry_run, group_by)
    _update_changelog(
        changelog_file,
        confluence,
        title_prefix,
        dry_run,
        processed=len(prepared),
        new=new_count,
        changed=changed_count,
        slipped=slipped,
    )
    if not dry_run:
        state.save()

    return RunResult(
        fetched=len(prepared),
        processed=len(prepared),
        published=published,
        skipped=0,
        unchanged=0,
        slipped=slipped,
        new=new_count,
        changed=changed_count,
        dashboards=dashboards,
        titles=[r.confluence_title for _, r, _ in prepared],
    )


def _publish_dashboards(
    state, confluence, title_prefix: str, dry_run: bool, group_by: str = "service"
) -> int:
    count = 0
    for quarter_label, body in quarter_dashboards(state.all_items(), group_by=group_by):
        title = dashboard_title(quarter_label, title_prefix)
        if dry_run or confluence is None:
            log.info("Dashboard (dry-run): %s", title)
            count += 1
            continue
        try:
            confluence.upsert_page(title, body)
            log.info("Dashboard published: %s", title)
            count += 1
        except Exception:
            log.exception("Dashboard write failed: %s", title)
    return count
