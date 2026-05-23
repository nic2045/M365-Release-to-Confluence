"""Run changelog: records what changed each run and renders a Confluence section."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ChangelogEntry:
    timestamp: str
    processed: int
    new: int
    changed: int
    slipped: int
    summary: str


class ChangelogStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: list[ChangelogEntry] = []

    def load(self) -> ChangelogStore:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [ChangelogEntry(**e) for e in raw]
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self._entries]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, *, processed: int, new: int, changed: int, slipped: int) -> ChangelogEntry:
        parts = []
        if new:
            parts.append(f"+{new} neu")
        if changed:
            parts.append(f"~{changed} geändert")
        if slipped:
            parts.append(f"⚠{slipped} verschoben")
        entry = ChangelogEntry(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            processed=processed,
            new=new,
            changed=changed,
            slipped=slipped,
            summary=", ".join(parts) or "keine Änderungen",
        )
        self._entries.append(entry)
        return entry

    def entries(self) -> list[ChangelogEntry]:
        return list(self._entries)


def render_changelog_body(entries: list[ChangelogEntry], limit: int = 30) -> str:
    recent = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(e.timestamp)}</td>"
        f"<td>{e.processed}</td>"
        f"<td>{html.escape(e.summary)}</td>"
        "</tr>"
        for e in recent
    )
    return (
        "<p>Automatisch generiert – nicht manuell bearbeiten.</p>"
        "<table><tbody>"
        "<tr><th>Zeitpunkt</th><th>Verarbeitet</th><th>Änderungen</th></tr>"
        f"{rows}"
        "</tbody></table>"
    )
