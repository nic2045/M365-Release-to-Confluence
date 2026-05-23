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

    @staticmethod
    def _check(resp) -> None:
        if resp.status_code == 401:
            raise ConfluenceError(
                "401 Unauthorized from Confluence. The Personal Access Token was "
                "rejected. Check that CONFLUENCE_TOKEN/ConfluencePAT is a valid, "
                "non-expired PAT (no extra spaces/newlines) and that this instance "
                "supports Bearer PAT auth (Confluence Data Center 7.9+)."
            )
        if resp.status_code == 403:
            raise ConfluenceError(
                "403 Forbidden from Confluence. The token authenticated but lacks "
                "permission for this space/page. Check CONFLUENCE_SPACE and the "
                "user's space permissions."
            )
        resp.raise_for_status()

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
        self._check(resp)
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
        self._check(resp)
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
        self._check(resp)
        return resp.json()

    def attach_file(
        self, page_id: str, filename: str, data: bytes, content_type: str = "application/xml"
    ) -> dict:
        """Create or update an attachment on a page (multipart upload)."""
        base = f"{self._api}/{page_id}/child/attachment"
        # multipart upload must not carry the session's JSON Content-Type
        headers = {"X-Atlassian-Token": "no-check", "Content-Type": None}
        files = {"file": (filename, data, content_type)}

        existing = self._session.get(
            base, params={"filename": filename}, headers={"Content-Type": None}, timeout=_TIMEOUT
        )
        self._check(existing)
        results = existing.json().get("results", [])
        if results:
            att_id = results[0]["id"]
            resp = self._session.post(
                f"{base}/{att_id}/data", files=files, headers=headers, timeout=_TIMEOUT
            )
        else:
            resp = self._session.post(base, files=files, headers=headers, timeout=_TIMEOUT)
        self._check(resp)
        return resp.json()
