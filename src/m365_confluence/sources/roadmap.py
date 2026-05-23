"""Microsoft 365 public roadmap source.

Reads the public release-communications feed (no authentication required).
This covers general upcoming rollouts that are not necessarily tenant-specific.
"""

from __future__ import annotations

from datetime import datetime

import requests

from m365_confluence.config import RoadmapConfig
from m365_confluence.models import ChangeItem

_TIMEOUT = 30


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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

        def _names(key: str) -> list[str]:
            return [t.get("tagName", "") for t in tags_container.get(key, []) if t.get("tagName")]

        products = _names("products")
        release_phases = _names("releasePhase")
        cloud_instances = _names("cloudInstances")
        platforms = _names("platforms")
        tags = [t for t in (release_phases + cloud_instances + platforms) if t]
        status = ""
        statuses = feature.get("status") or feature.get("featureStatus")
        if isinstance(statuses, list) and statuses:
            status = (
                statuses[0].get("tagName", "")
                if isinstance(statuses[0], dict)
                else str(statuses[0])
            )
        elif isinstance(statuses, str):
            status = statuses
        return ChangeItem(
            id=feature_id,
            source="roadmap",
            title=feature.get("title", "").strip(),
            body=feature.get("description", ""),
            url=f"https://www.microsoft.com/microsoft-365/roadmap?featureid={feature_id}",
            category="roadmap",
            status=status,
            products=products,
            tags=tags,
            release_phases=release_phases,
            cloud_instances=cloud_instances,
            platforms=platforms,
            created=_parse_dt(feature.get("created")),
            last_modified=_parse_dt(feature.get("modified") or feature.get("created")),
        )
