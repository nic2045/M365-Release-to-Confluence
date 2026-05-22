"""Combine items from multiple sources, dedupe, and filter."""

from __future__ import annotations

from datetime import datetime, timezone

from m365_confluence.models import ChangeItem


def aggregate(
    item_lists: list[list[ChangeItem]],
    *,
    since: datetime | None = None,
    limit: int | None = None,
) -> list[ChangeItem]:
    """Merge, dedupe by source+id, optionally filter by ``since`` and cap to ``limit``.

    Items are sorted newest-first by ``last_modified`` (items without a date sort last).
    """
    seen: set[str] = set()
    merged: list[ChangeItem] = []
    for items in item_lists:
        for item in items:
            key = item.dedupe_key()
            if key in seen:
                continue
            if (
                since is not None
                and item.last_modified is not None
                and item.last_modified < _ensure_aware(since)
            ):
                continue
            seen.add(key)
            merged.append(item)

    merged.sort(key=_sort_key, reverse=True)
    if limit is not None:
        merged = merged[:limit]
    return merged


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _sort_key(item: ChangeItem) -> datetime:
    if item.last_modified is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _ensure_aware(item.last_modified)
