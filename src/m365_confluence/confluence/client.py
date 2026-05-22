"""Minimal Confluence Server / Data Center REST client (PAT auth).

Uses the classic ``/rest/api/content`` endpoints with Bearer Personal Access
Token authentication, and creates or updates a page per change item so reruns
are idempotent (matched by title within the target space).
"""

from __future__ import annotations

import requests

from m365_confluence.config import ConfluenceConfig

_TIMEOUT = 30


class ConfluenceError(RuntimeError):
    pass


class ConfluenceClient:
    def __init__(self, config: ConfluenceConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
            }
        )

    @property
    def _api(self) -> str:
        return f"{self._config.base_url}/rest/api/content"

    def find_page(self, title: str) -> dict | None:
        resp = self._session.get(
            self._api,
            params={
                "title": title,
                "spaceKey": self._config.space_key,
                "expand": "version",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None

    def upsert_page(self, title: str, body_storage: str) -> dict:
        """Create the page, or update it in place if it already exists."""
        existing = self.find_page(title)
        if existing:
            return self._update(existing, title, body_storage)
        return self._create(title, body_storage)

    def _create(self, title: str, body_storage: str) -> dict:
        payload: dict = {
            "type": "page",
            "title": title,
            "space": {"key": self._config.space_key},
            "body": {"storage": {"value": body_storage, "representation": "storage"}},
        }
        if self._config.parent_page_id:
            payload["ancestors"] = [{"id": self._config.parent_page_id}]
        resp = self._session.post(self._api, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _update(self, existing: dict, title: str, body_storage: str) -> dict:
        page_id = existing["id"]
        next_version = existing.get("version", {}).get("number", 1) + 1
        payload = {
            "type": "page",
            "title": title,
            "version": {"number": next_version},
            "body": {"storage": {"value": body_storage, "representation": "storage"}},
        }
        resp = self._session.put(f"{self._api}/{page_id}", json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
