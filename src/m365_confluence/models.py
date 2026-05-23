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
    severity: str = ""  # Message Center severity, e.g. "normal", "high", "critical"
    status: str = ""  # roadmap rollout stage, e.g. "In development", "Rolling out", "Launched"
    products: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    release_phases: list[str] = field(
        default_factory=list
    )  # MS channels, e.g. "General Availability"
    cloud_instances: list[str] = field(
        default_factory=list
    )  # e.g. "Worldwide (Standard Multi-Tenant)"
    platforms: list[str] = field(default_factory=list)
    created: datetime | None = None
    last_modified: datetime | None = None
    release_date: datetime | None = None  # MS-provided availability/GA date (roadmap)
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
    cab_required: bool = False  # should the Change Advisory Board review this?
    cab_recommendation: str = ""  # recommendation for the Change Advisory Board
    areas: list[str] = field(default_factory=list)  # End User / Admin · IT / Security / Compliance
    slipped: bool = False  # target quarter moved later than previously seen
    previous_quarter: str = ""  # the earlier target quarter, when slipped
    confluence_title: str = ""
    confluence_body: str = ""  # Confluence storage-format (XHTML)
