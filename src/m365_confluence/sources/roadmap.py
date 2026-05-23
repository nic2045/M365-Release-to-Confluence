"""Microsoft 365 public roadmap source.

Reads the public release-communications feed (no authentication required).
Supports the v2 schema (flat ``products``/``cloudInstances``/``platforms``/
``releaseRings`` plus an ``availabilities`` collection of ``{ring, year,
month}``) as well as the older v1 ``tagsContainer`` shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

import requests

from m365_confluence.config import RoadmapConfig
from m365_confluence.models import ChangeItem
from m365_confluence.quarters import MONTHS

_TIMEOUT = 30


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return _parse_year_month(value)


def _parse_year_month(value: str | None) -> datetime | None:
    """Parse 'YYYY-MM' (with optional day) into a UTC datetime."""
    if not value:
        return None
    parts = value.strip().split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
    except (ValueError, IndexError):
        return None
    if 1 <= month <= 12:
        return datetime(year, month, 1, tzinfo=timezone.utc)
    return None


def _month_num(value: object) -> int | None:
    s = str(value or "").strip().lower()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None
    return MONTHS.get(s)


def _to_strs(value: object) -> list[str]:
    """Normalise a list whose items are strings (v2) or {tagName/name} dicts (v1)."""
    out: list[str] = []
    if not isinstance(value, list):
        return out
    for v in value:
        name = (v.get("tagName") or v.get("name") or "") if isinstance(v, dict) else str(v)
        if name:
            out.append(name)
    return out


def _availability_date(feature: dict) -> datetime | None:
    """MS target date: prefer the GA availability (ring/year/month), else GA date string."""
    avails = feature.get("availabilities")
    parsed: list[tuple[bool, datetime]] = []
    if isinstance(avails, list):
        for a in avails:
            if not isinstance(a, dict):
                continue
            year = a.get("year")
            month = _month_num(a.get("month"))
            if isinstance(year, int) and month:
                is_ga = "general availability" in str(a.get("ring", "")).lower()
                parsed.append((is_ga, datetime(year, month, 1, tzinfo=timezone.utc)))
    if parsed:
        # Prefer a GA ring; otherwise the earliest date.
        ga = [d for is_ga, d in parsed if is_ga]
        return min(ga) if ga else min(d for _, d in parsed)
    return _parse_dt(feature.get("generalAvailabilityDate"))


def _features(payload: object) -> list[dict]:
    """Accept a top-level list (v1) or an object wrapping the list (v2 variants)."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("value", "features", "results", "items", "data"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return inner
    return []


class RoadmapSource:
    name = "roadmap"

    def __init__(self, config: RoadmapConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def fetch(self) -> list[ChangeItem]:
        resp = self._session.get(self._config.api_url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return [self._map(feature) for feature in _features(resp.json())]

    @staticmethod
    def _map(feature: dict) -> ChangeItem:
        feature_id = str(feature.get("id", ""))
        tags_container = feature.get("tagsContainer") or {}

        def _field(v2_key: str, v1_key: str) -> list[str]:
            # v2: flat list under v2_key; v1: list of dicts under tagsContainer[v1_key].
            if isinstance(feature.get(v2_key), list):
                return _to_strs(feature.get(v2_key))
            return _to_strs(tags_container.get(v1_key))

        products = _field("products", "products")
        release_phases = _field("releaseRings", "releasePhase")
        cloud_instances = _field("cloudInstances", "cloudInstances")
        platforms = _field("platforms", "platforms")
        tags = [t for t in (release_phases + cloud_instances + platforms) if t]

        status = ""
        statuses = feature.get("status") or feature.get("featureStatus")
        if isinstance(statuses, list) and statuses:
            first = statuses[0]
            status = first.get("tagName", "") if isinstance(first, dict) else str(first)
        elif isinstance(statuses, str):
            status = statuses

        more_info = feature.get("moreInfoUrls")
        url = (
            more_info[0]
            if isinstance(more_info, list) and more_info
            else f"https://www.microsoft.com/microsoft-365/roadmap?featureid={feature_id}"
        )

        return ChangeItem(
            id=feature_id,
            source="roadmap",
            title=(feature.get("title") or "").strip(),
            body=feature.get("description", ""),
            url=url,
            category="roadmap",
            status=status,
            products=products,
            tags=tags,
            release_phases=release_phases,
            cloud_instances=cloud_instances,
            platforms=platforms,
            created=_parse_dt(feature.get("created")),
            last_modified=_parse_dt(feature.get("modified") or feature.get("created")),
            release_date=_availability_date(feature),
        )
