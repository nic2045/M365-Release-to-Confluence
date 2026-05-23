"""Source protocol."""

from __future__ import annotations

from typing import Protocol

from m365_confluence.models import ChangeItem


class Source(Protocol):
    """A source of M365 change items."""

    name: str

    def fetch(self) -> list[ChangeItem]:
        """Return all available change items from this source."""
        ...
