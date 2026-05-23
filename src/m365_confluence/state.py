"""Local JSON state store for incremental runs and slip detection.

Tracks, per change item, a content hash (to skip unchanged items and save
tokens) plus the last known target quarter and the fields needed to render the
quarterly dashboard even when most items are skipped in a given run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from m365_confluence.models import ChangeItem, ProcessedItem


@dataclass
class ItemState:
    key: str
    content_hash: str
    title: str = ""
    confluence_title: str = ""
    url: str = ""
    status: str = ""
    products: list[str] = field(default_factory=list)
    target_quarter: str = ""
    decision: str = ""
    cab_required: bool = False
    cab_recommendation: str = ""
    areas: list[str] = field(default_factory=list)
    data_protection_impact: bool = False
    it_landscape_impact: bool = False
    config_change_required: bool = False
    kbv_change_required: bool = False
    summary: str = ""
    has_page: bool = False
    slipped: bool = False
    previous_quarter: str = ""
    quarter_history: list[str] = field(default_factory=list)
    last_seen: str = ""


def content_hash(item: ChangeItem) -> str:
    last_modified = item.last_modified.isoformat() if item.last_modified else ""
    payload = "\n".join([item.title, item.body, item.status, last_modified])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._items: dict[str, ItemState] = {}

    def load(self) -> StateStore:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for key, data in raw.get("items", {}).items():
                self._items[key] = ItemState(**data)
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": {k: asdict(v) for k, v in self._items.items()}}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str) -> ItemState | None:
        return self._items.get(key)

    def is_unchanged(self, item: ChangeItem) -> bool:
        existing = self._items.get(item.dedupe_key())
        return existing is not None and existing.content_hash == content_hash(item)

    def record(
        self,
        item: ChangeItem,
        processed: ProcessedItem,
        *,
        has_page: bool = False,
        quarter_history: list[str] | None = None,
    ) -> None:
        self._items[item.dedupe_key()] = ItemState(
            key=item.dedupe_key(),
            content_hash=content_hash(item),
            title=item.title,
            confluence_title=processed.confluence_title,
            url=item.url,
            status=item.status,
            products=list(item.products),
            target_quarter=processed.target_quarter,
            decision=processed.decision,
            cab_required=processed.cab_required,
            cab_recommendation=processed.cab_recommendation,
            areas=list(processed.areas),
            data_protection_impact=processed.data_protection_impact,
            it_landscape_impact=processed.it_landscape_impact,
            config_change_required=processed.config_change_required,
            kbv_change_required=processed.kbv_change_required,
            summary=processed.summary,
            has_page=has_page,
            slipped=processed.slipped,
            previous_quarter=processed.previous_quarter,
            quarter_history=list(quarter_history or []),
            last_seen=datetime.now(timezone.utc).isoformat(),
        )

    def touch(self, key: str) -> None:
        existing = self._items.get(key)
        if existing is not None:
            existing.last_seen = datetime.now(timezone.utc).isoformat()

    def all_items(self) -> list[ItemState]:
        return list(self._items.values())
