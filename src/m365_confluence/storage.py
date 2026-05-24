"""Pluggable persistence backends for state and review drafts.

Standalone (CLI) keeps its JSON files via the file backends below. When the
module is embedded in a multi-user host (the Weekly app), the host injects its
own DB-backed, per-user backends so each user's state/drafts live in the shared
database instead of a shared file on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StateBackend(Protocol):
    """Raw persistence for the item-state blob (``{"items": {...}}``)."""

    def read(self) -> dict: ...

    def write(self, payload: dict) -> None: ...


@runtime_checkable
class DraftsBackend(Protocol):
    """Raw persistence for the review drafts list."""

    def read(self) -> list[dict]: ...

    def write(self, drafts: list[dict]) -> None: ...


class JsonFileStateBackend:
    """Default state backend: a single JSON file on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


class JsonFileDraftsBackend:
    """Default drafts backend: a single ``review.json``-style file on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return raw.get("items", [])

    def write(self, drafts: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"items": drafts}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
