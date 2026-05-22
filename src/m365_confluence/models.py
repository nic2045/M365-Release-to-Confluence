"""Shared data models for the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChangeItem:
    """A single M365 change or upcoming rollout, normalised across sources."""

    id: str
    source: str  # "message_center" | "roadmap"
    title: str
    body: str  # raw text/HTML as delivered by the source
    url: str = ""
    category: str = ""  # e.g. "planForChange", "stayInformed", "preventOrFixIssue"
    status: str = ""  # roadmap rollout status, e.g. "In development"
    products: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    last_modified: datetime | None = None
    act_by: datetime | None = None

    def dedupe_key(self) -> str:
        return f"{self.source}:{self.id}"


@dataclass
class ProcessedItem:
    """An LLM-processed change, ready to publish to Confluence."""

    source_item: ChangeItem
    summary: str
    impact: str
    audience: str
    action_items: list[str] = field(default_factory=list)
    recommended_action: str = ""
    target_quarter: str = ""  # e.g. "Q3 2026"; "" if unknown
    decision: str = ""  # Activate | Deactivate | Communicate | Monitor
    decision_rationale: str = ""
    slipped: bool = False  # target quarter moved later than previously seen
    previous_quarter: str = ""  # the earlier target quarter, when slipped
    confluence_title: str = ""
    confluence_body: str = ""  # Confluence storage-format (XHTML)
