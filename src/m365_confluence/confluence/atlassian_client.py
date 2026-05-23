"""Confluence backend using atlassian-python-api (optional; PAT/Bearer auth).

Install with: pip install -e ".[atlassian]"
Activate with: CONFLUENCE_BACKEND=atlassian
"""

from __future__ import annotations

from m365_confluence.config import ConfluenceConfig


class AtlassianConfluenceClient:
    """Same upsert_page interface as the built-in client, backed by the SDK."""

    def __init__(self, config: ConfluenceConfig, client: object | None = None) -> None:
        self._config = config
        if client is not None:
            self._c = client
        else:
            from atlassian import Confluence

            self._c = Confluence(url=config.base_url, token=config.token)

    def upsert_page(self, title: str, body_storage: str) -> dict:
        space = self._config.space_key
        existing = self._c.get_page_by_title(space=space, title=title)
        if existing:
            return self._c.update_page(
                page_id=existing["id"],
                title=title,
                body=body_storage,
                representation="storage",
            )
        return self._c.create_page(
            space=space,
            title=title,
            body=body_storage,
            parent_id=self._config.parent_page_id or None,
            representation="storage",
        )
