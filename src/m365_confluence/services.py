"""Map M365 products to internal IT services.

Default buckets follow the house concept: Exchange Online, SharePoint Online and
Teams are services (backend + clients), Defender/Purview/Information Protection
form a Compliance/Security service, everything else is the general M365 Admin
service. Override via a JSON file referenced by ``SERVICE_MAP_FILE`` (keys are
lowercase product substrings, values are service names).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SERVICE = "Allgemein / M365 Admin"

# Order matters: longer / more specific substrings first.
_DEFAULT_MAP: list[tuple[str, str]] = [
    ("sharepoint syntex", "SharePoint Online"),
    ("sharepoint", "SharePoint Online"),
    ("onedrive", "SharePoint Online"),
    ("outlook", "Exchange Online"),
    ("exchange", "Exchange Online"),
    ("microsoft teams", "Teams"),
    ("teams", "Teams"),
    ("planner", "Teams"),
    ("to do", "Teams"),
    ("whiteboard", "Teams"),
    ("defender for office", "Compliance/Security"),
    ("purview", "Compliance/Security"),
    ("information protection", "Compliance/Security"),
]


def _load_overrides() -> list[tuple[str, str]]:
    path = os.getenv("SERVICE_MAP_FILE")
    if not path or not Path(path).exists():
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    # Longest substrings first so specific rules win.
    return sorted(
        ((str(k).lower(), str(v)) for k, v in data.items()),
        key=lambda kv: len(kv[0]),
        reverse=True,
    )


def service_for(product: str) -> str:
    p = (product or "").lower()
    for sub, service in _load_overrides() + _DEFAULT_MAP:
        if sub in p:
            return service
    return DEFAULT_SERVICE


def services_for(products: list[str]) -> list[str]:
    """Distinct services for an item's products (stable order); default if none."""
    out: list[str] = []
    for product in products or []:
        svc = service_for(product)
        if svc not in out:
            out.append(svc)
    return out or [DEFAULT_SERVICE]
