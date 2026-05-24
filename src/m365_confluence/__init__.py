"""Read M365 changes/rollouts, summarise them with an LLM, publish to Confluence."""

from __future__ import annotations

__version__ = "1.2.0"  # x-release-please-version

from m365_confluence.models import ChangeItem, ProcessedItem

__all__ = ["ChangeItem", "ProcessedItem", "__version__"]
