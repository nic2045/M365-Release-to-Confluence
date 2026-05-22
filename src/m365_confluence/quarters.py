"""Quarter parsing, derivation and comparison helpers.

A normalised quarter label looks like ``"Q3 2026"``. ``""`` means unknown.
"""

from __future__ import annotations

import re
from datetime import datetime

from m365_confluence.models import ChangeItem

UNSCHEDULED = "Unscheduled"

_Q_RE = re.compile(r"\bQ\s*([1-4])\s*(?:CY)?\s*(20\d{2})\b", re.IGNORECASE)
_YEAR_Q_RE = re.compile(r"\b(20\d{2})\s*Q\s*([1-4])\b", re.IGNORECASE)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_YEAR_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b",
    re.IGNORECASE,
)


def quarter_from_date(dt: datetime) -> str:
    return f"Q{(dt.month - 1) // 3 + 1} {dt.year}"


def normalize_quarter(text: str) -> str:
    """Extract the first quarter mentioned in ``text`` as ``"Qn YYYY"`` or ``""``."""
    if not text:
        return ""
    m = _Q_RE.search(text)
    if m:
        return f"Q{m.group(1)} {m.group(2)}"
    m = _YEAR_Q_RE.search(text)
    if m:
        return f"Q{m.group(2)} {m.group(1)}"
    m = _MONTH_YEAR_RE.search(text)
    if m:
        month = _MONTHS[m.group(1).lower()]
        return f"Q{(month - 1) // 3 + 1} {m.group(2)}"
    return ""


def derive_quarter(item: ChangeItem) -> str:
    """Best-effort target quarter from the item's text or its deadline date."""
    for text in (item.title, item.body):
        label = normalize_quarter(text)
        if label:
            return label
    if item.act_by is not None:
        return quarter_from_date(item.act_by)
    return ""


def quarter_key(label: str) -> tuple[int, int]:
    """Sortable key; unknown/unscheduled sorts last."""
    m = re.match(r"Q([1-4])\s+(20\d{2})", label or "")
    if not m:
        return (9999, 9)
    return (int(m.group(2)), int(m.group(1)))
