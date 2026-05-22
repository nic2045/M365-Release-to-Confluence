"""Data sources for M365 changes and rollouts."""

from __future__ import annotations

from m365_confluence.sources.aggregate import aggregate
from m365_confluence.sources.base import Source
from m365_confluence.sources.message_center import MessageCenterSource
from m365_confluence.sources.roadmap import RoadmapSource

__all__ = ["MessageCenterSource", "RoadmapSource", "Source", "aggregate"]
