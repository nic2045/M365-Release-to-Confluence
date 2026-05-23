"""Confluence Server / Data Center client."""

from __future__ import annotations

from m365_confluence.config import ConfluenceConfig
from m365_confluence.confluence.client import ConfluenceClient


def build_confluence(config: ConfluenceConfig):
    """Return a Confluence client for the configured backend.

    Both clients expose ``upsert_page(title, body_storage)``.
    """
    if config.backend == "atlassian":
        from m365_confluence.confluence.atlassian_client import AtlassianConfluenceClient

        return AtlassianConfluenceClient(config)
    return ConfluenceClient(config)


__all__ = ["ConfluenceClient", "build_confluence"]
