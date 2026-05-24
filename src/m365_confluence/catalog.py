"""Fetch-once catalog: the local cache of every M365 item.

The catalog decouples the expensive LLM step from fetching and browsing:

* **Sync (stage A, no LLM):** fetch *all* items once, label them deterministically
  (service/product/quarter/change-type via ``review.source_dict``), diff against
  the previous catalog to flag *new* / *changed* / *unchanged*, and persist. Meant
  to run weekly so the UI can show what moved without re-fetching every time.
* **Enrich (stage B, LLM):** run the model only for the items the user selects,
  caching the result on the entry so the same item is never paid for twice.
* **Publish:** push the enriched, non-ignored entries to Confluence (reusing the
  review publish path) and stamp each entry with when it was published.

A catalog entry is a superset of a review draft (same ``source``/``edit`` shape),
so the review serialisers round-trip both.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from m365_confluence.ai import build_provider, process_item
from m365_confluence.config import Config
from m365_confluence.review import edit_dict, item_from_source, source_dict
from m365_confluence.sources import aggregate
from m365_confluence.state import content_hash
from m365_confluence.storage import CatalogBackend, JsonFileCatalogBackend

log = logging.getLogger("m365_confluence")

DEFAULT_CATALOG_FILE = "m365_catalog.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SyncResult:
    total: int
    new: int
    changed: int
    unchanged: int
    removed: int


@dataclass
class EnrichResult:
    enriched: int
    skipped: int
    errors: list[tuple[str, str]] = field(default_factory=list)


class Catalog:
    """In-memory view of the catalog, persisted via a pluggable backend."""

    def __init__(
        self,
        path: str | None = None,
        *,
        backend: CatalogBackend | None = None,
    ) -> None:
        if backend is None:
            backend = JsonFileCatalogBackend(path or DEFAULT_CATALOG_FILE)
        self._backend = backend
        self.items: dict[str, dict] = {}
        self.synced_at: str = ""

    def load(self) -> Catalog:
        raw = self._backend.read() or {}
        self.items = dict(raw.get("items", {}))
        self.synced_at = raw.get("synced_at", "")
        return self

    def save(self) -> None:
        self._backend.write({"synced_at": self.synced_at, "items": self.items})

    def entries(self) -> list[dict]:
        """Catalog entries as a list (most recently modified source first)."""
        return sorted(
            self.items.values(),
            key=lambda e: (e["source"].get("last_modified") or "", e.get("first_seen", "")),
            reverse=True,
        )


def sync_catalog(
    config: Config,
    *,
    catalog_file: str = DEFAULT_CATALOG_FILE,
    catalog: Catalog | None = None,
    since_days: int | None = None,
) -> SyncResult:
    """Fetch all items, label them, diff against the stored catalog, persist."""
    # Imported here to avoid a module-load cycle (pipeline imports nothing from us).
    from m365_confluence.pipeline import collect

    since = None
    if since_days is not None:
        from datetime import timedelta

        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    items = aggregate(collect(config), since=since, limit=None)
    cat = (catalog if catalog is not None else Catalog(catalog_file)).load()
    now = _now()
    seen: set[str] = set()
    new = changed = unchanged = 0

    for item in items:
        key = item.dedupe_key()
        seen.add(key)
        digest = content_hash(item)
        labels = source_dict(item)
        existing = cat.items.get(key)
        if existing is None:
            new += 1
            cat.items[key] = {
                "key": key,
                "source": labels,
                "content_hash": digest,
                "change_status": "new",
                "first_seen": now,
                "last_seen": now,
                "enriched": False,
                "stale": False,
                "edit": None,
                "make_page": False,
                "ignored": False,
                "published": False,
                "published_at": "",
                "removed": False,
            }
        elif existing.get("content_hash") != digest:
            changed += 1
            existing["source"] = labels
            existing["content_hash"] = digest
            existing["change_status"] = "changed"
            existing["last_seen"] = now
            existing["removed"] = False
            # Content moved on; any cached enrichment is now outdated.
            if existing.get("enriched"):
                existing["stale"] = True
        else:
            unchanged += 1
            existing["change_status"] = "unchanged"
            existing["last_seen"] = now
            existing["removed"] = False

    removed = 0
    for key, entry in cat.items.items():
        if key not in seen and not entry.get("removed"):
            entry["removed"] = True
            entry["change_status"] = "removed"
            removed += 1

    cat.synced_at = now
    cat.save()
    log.info(
        "Catalog sync: total=%d new=%d changed=%d unchanged=%d removed=%d",
        len(items),
        new,
        changed,
        unchanged,
        removed,
    )
    return SyncResult(
        total=len(items), new=new, changed=changed, unchanged=unchanged, removed=removed
    )


def enrich_catalog(
    config: Config,
    keys: list[str],
    *,
    catalog_file: str = DEFAULT_CATALOG_FILE,
    catalog: Catalog | None = None,
    title_prefix: str = "[M365] ",
    force: bool = False,
) -> EnrichResult:
    """Run the LLM for the selected entries only; cache the result on each entry."""
    from m365_confluence.pipeline import _is_fatal_provider_error

    cat = (catalog if catalog is not None else Catalog(catalog_file)).load()
    provider = build_provider(config.ai)
    enriched = 0
    skipped = 0
    errors: list[tuple[str, str]] = []

    targets = [k for k in keys if k in cat.items]
    total = len(targets)
    for index, key in enumerate(targets, start=1):
        entry = cat.items[key]
        if entry.get("enriched") and not entry.get("stale") and not force:
            skipped += 1
            continue
        item = item_from_source(entry["source"])
        log.info("[%d/%d] Enriching %s ...", index, total, key)
        try:
            result = process_item(provider, item, config.ai.output_language, config.ai.org_context)
        except Exception as exc:  # noqa: BLE001 - surface per-item, abort on fatal
            errors.append((key, str(exc)))
            if _is_fatal_provider_error(exc):
                log.error("Aborting enrichment: provider error — %s", str(exc).splitlines()[0])
                break
            log.exception("[%d/%d] Enrichment failed for %s", index, total, key)
            continue
        result.confluence_title = f"{title_prefix}{result.confluence_title}"
        entry["edit"] = edit_dict(result)
        entry["enriched"] = True
        entry["stale"] = False
        enriched += 1

    cat.save()
    log.info("Catalog enrich: enriched=%d skipped=%d errors=%d", enriched, skipped, len(errors))
    return EnrichResult(enriched=enriched, skipped=skipped, errors=errors)


def publish_catalog(
    config: Config,
    *,
    catalog_file: str = DEFAULT_CATALOG_FILE,
    catalog: Catalog | None = None,
    keys: list[str] | None = None,
    dry_run: bool = False,
    group_by: str = "service",
    title_prefix: str = "[M365] ",
    state_file: str = "m365_state.json",
    changelog_file: str = "m365_changelog.json",
):
    """Publish enriched, non-ignored entries to Confluence; stamp ``published_at``."""
    from m365_confluence.pipeline import publish_drafts

    cat = (catalog if catalog is not None else Catalog(catalog_file)).load()
    selectable = [
        entry
        for key, entry in cat.items.items()
        if (keys is None or key in keys)
        and entry.get("enriched")
        and entry.get("edit")
        and not entry.get("ignored")
    ]
    drafts = [
        {"source": e["source"], "edit": e["edit"], "make_page": e.get("make_page", False)}
        for e in selectable
    ]
    result = publish_drafts(
        config,
        drafts,
        dry_run=dry_run,
        group_by=group_by,
        title_prefix=title_prefix,
        state_file=state_file,
        changelog_file=changelog_file,
    )
    if not dry_run:
        now = _now()
        for entry in selectable:
            entry["published"] = True
            entry["published_at"] = now
        cat.save()
    return result


def debug_rows(catalog: Catalog) -> list[dict]:
    """Flat rows for the debug listing: lifecycle timestamps + status per item."""
    rows: list[dict] = []
    for entry in catalog.entries():
        s = entry["source"]
        rows.append(
            {
                "key": entry["key"],
                "source": s.get("source", ""),
                "id": s.get("id", ""),
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "status": s.get("status", ""),
                "target_quarter": s.get("target_quarter", ""),
                "services": s.get("services", []),
                "products": s.get("products", []),
                "created": s.get("created"),
                "last_modified": s.get("last_modified"),
                "first_seen": entry.get("first_seen", ""),
                "last_seen": entry.get("last_seen", ""),
                "change_status": entry.get("change_status", ""),
                "enriched": bool(entry.get("enriched")),
                "stale": bool(entry.get("stale")),
                "ignored": bool(entry.get("ignored")),
                "published": bool(entry.get("published")),
                "published_at": entry.get("published_at", ""),
                "removed": bool(entry.get("removed")),
                "confluence_title": (entry.get("edit") or {}).get("confluence_title", ""),
            }
        )
    return rows
