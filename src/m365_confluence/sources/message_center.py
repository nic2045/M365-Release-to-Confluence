"""Microsoft 365 Message Center source via Microsoft Graph.

Reads tenant-specific service announcements (current changes and upcoming
rollouts) from ``/admin/serviceAnnouncement/messages``.

Requires an Entra ID app registration with the application permission
``ServiceMessage.Read.All`` (admin consent granted).
"""

from __future__ import annotations

from datetime import datetime

import requests

from m365_confluence.config import GraphConfig
from m365_confluence.models import ChangeItem

_TIMEOUT = 30


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class MessageCenterSource:
    name = "message_center"

    def __init__(self, config: GraphConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def _token(self) -> str:
        resp = self._session.post(
            f"{self._config.authority}/{self._config.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def fetch(self) -> list[ChangeItem]:
        token = self._token()
        headers = {"Authorization": f"Bearer {token}"}
        url: str | None = f"{self._config.base_url}/admin/serviceAnnouncement/messages"
        items: list[ChangeItem] = []
        while url:
            resp = self._session.get(url, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            items.extend(self._map(m) for m in payload.get("value", []))
            url = payload.get("@odata.nextLink")
        return items

    @staticmethod
    def _map(message: dict) -> ChangeItem:
        body = message.get("body", {}) or {}
        services = message.get("services") or []
        details = message.get("details") or []
        tags = [d.get("value", "") for d in details if d.get("value")]
        if message.get("isMajorChange"):
            tags.append("MajorChange")
        return ChangeItem(
            id=str(message.get("id", "")),
            source="message_center",
            title=message.get("title", "").strip(),
            body=body.get("content", ""),
            url="https://admin.microsoft.com/Adminportal/Home#/MessageCenter",
            category=message.get("category", ""),
            products=list(services),
            tags=tags,
            last_modified=_parse_dt(message.get("lastModifiedDateTime")),
            act_by=_parse_dt(message.get("actionRequiredByDateTime")),
        )
