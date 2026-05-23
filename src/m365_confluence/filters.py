"""Deterministic relevance pre-filters applied before the LLM (token-saving)."""

from __future__ import annotations

from collections.abc import Sequence

from m365_confluence.models import ChangeItem

_LIVE_STATUSES = ("rolling out", "launched", "generally available", "live")


def is_rollout_or_live(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in _LIVE_STATUSES)


def is_worldwide(item: ChangeItem) -> bool:
    """True if the item has no cloud-instance info or includes a Worldwide instance.

    Items without cloud-instance data (e.g. Message Center posts) always pass.
    """
    if not item.cloud_instances:
        return True
    return any("worldwide" in c.lower() for c in item.cloud_instances)


def matches(
    item: ChangeItem,
    *,
    major_only: bool = False,
    action_required: bool = False,
    products: Sequence[str] | None = None,
    categories: Sequence[str] | None = None,
    worldwide_only: bool = False,
) -> bool:
    """AND across filter types; OR within products/categories. Empty filter = pass."""
    if major_only and "MajorChange" not in item.tags:
        return False
    if action_required and item.act_by is None:
        return False
    if worldwide_only and not is_worldwide(item):
        return False
    if products:
        haystack = [p.lower() for p in item.products]
        if not any(want in p for want in products for p in haystack):
            return False
    return not (categories and item.category.lower() not in categories)


def apply_filters(
    items: list[ChangeItem],
    *,
    major_only: bool = False,
    action_required: bool = False,
    products: Sequence[str] | None = None,
    categories: Sequence[str] | None = None,
    worldwide_only: bool = False,
) -> list[ChangeItem]:
    products = [p.lower() for p in products] if products else None
    categories = [c.lower() for c in categories] if categories else None
    return [
        item
        for item in items
        if matches(
            item,
            major_only=major_only,
            action_required=action_required,
            products=products,
            categories=categories,
            worldwide_only=worldwide_only,
        )
    ]
