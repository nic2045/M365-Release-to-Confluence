"""Review drafts: export processed items to JSON for human edit, then publish.

This enables the "draft -> edit -> publish" workflow: a run can write
``review.json`` instead of publishing; after editing (CLI or the web UI), the
drafts are published to Confluence without calling the LLM again.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from m365_confluence.models import ChangeItem, ProcessedItem


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _pdt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _change_type(item: ChangeItem) -> str:
    if (
        item.created
        and item.last_modified
        and (item.last_modified - item.created).total_seconds() > 86400
    ):
        return "Aktualisiert"
    return "Neu"


def draft_from(item: ChangeItem, processed: ProcessedItem, make_page: bool) -> dict:
    return {
        "key": item.dedupe_key(),
        "source": {
            "id": item.id,
            "source": item.source,
            "title": item.title,
            "body": item.body,
            "url": item.url,
            "category": item.category,
            "severity": item.severity,
            "status": item.status,
            "products": list(item.products),
            "tags": list(item.tags),
            "release_phases": list(item.release_phases),
            "cloud_instances": list(item.cloud_instances),
            "change_type": _change_type(item),
            "created": _dt(item.created),
            "last_modified": _dt(item.last_modified),
            "act_by": _dt(item.act_by),
        },
        "edit": {
            "confluence_title": processed.confluence_title,
            "summary": processed.summary,
            "impact": processed.impact,
            "audience": processed.audience,
            "recommended_action": processed.recommended_action,
            "action_items": list(processed.action_items),
            "target_quarter": processed.target_quarter,
            "decision": processed.decision,
            "decision_rationale": processed.decision_rationale,
            "cab_required": processed.cab_required,
            "cab_recommendation": processed.cab_recommendation,
        },
        "make_page": make_page,
        "ignored": False,
    }


def draft_to(draft: dict) -> tuple[ChangeItem, ProcessedItem, bool]:
    s = draft["source"]
    e = draft["edit"]
    item = ChangeItem(
        id=s["id"],
        source=s["source"],
        title=s.get("title", ""),
        body=s.get("body", ""),
        url=s.get("url", ""),
        category=s.get("category", ""),
        severity=s.get("severity", ""),
        status=s.get("status", ""),
        products=list(s.get("products") or []),
        tags=list(s.get("tags") or []),
        release_phases=list(s.get("release_phases") or []),
        cloud_instances=list(s.get("cloud_instances") or []),
        created=_pdt(s.get("created")),
        last_modified=_pdt(s.get("last_modified")),
        act_by=_pdt(s.get("act_by")),
    )
    processed = ProcessedItem(
        source_item=item,
        summary=e.get("summary", ""),
        impact=e.get("impact", ""),
        audience=e.get("audience", ""),
        action_items=list(e.get("action_items") or []),
        recommended_action=e.get("recommended_action", ""),
        target_quarter=e.get("target_quarter", ""),
        decision=e.get("decision", ""),
        decision_rationale=e.get("decision_rationale", ""),
        cab_required=bool(e.get("cab_required")),
        cab_recommendation=e.get("cab_recommendation", ""),
        confluence_title=e.get("confluence_title", ""),
    )
    return item, processed, bool(draft.get("make_page", False))


def save_drafts(path: str | Path, drafts: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": drafts}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_drafts(path: str | Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw.get("items", [])
