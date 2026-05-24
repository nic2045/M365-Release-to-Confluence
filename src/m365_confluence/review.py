"""Review drafts: export processed items to JSON for human edit, then publish.

This enables the "draft -> edit -> publish" workflow: a run can write
``review.json`` instead of publishing; after editing (CLI or the web UI), the
drafts are published to Confluence without calling the LLM again.

The ``source_dict``/``edit_dict`` (and their inverses) are the shared
serialisation contract reused by the catalog (``catalog.py``): a catalog entry
is a draft plus sync metadata, so the same converters round-trip both.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.quarters import derive_quarter
from m365_confluence.services import service_for, services_for


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


def source_dict(item: ChangeItem) -> dict:
    """Serialise the raw source item plus deterministic labels (no LLM)."""
    return {
        "id": item.id,
        "source": item.source,
        "title": item.title,
        "body": item.body,
        "url": item.url,
        "category": item.category,
        "severity": item.severity,
        "status": item.status,
        "products": list(item.products),
        "services": services_for(item.products),
        "product_services": {p: service_for(p) for p in item.products},
        "tags": list(item.tags),
        "release_phases": list(item.release_phases),
        "cloud_instances": list(item.cloud_instances),
        "change_type": _change_type(item),
        "target_quarter": derive_quarter(item),
        "created": _dt(item.created),
        "last_modified": _dt(item.last_modified),
        "release_date": _dt(item.release_date),
        "act_by": _dt(item.act_by),
    }


def edit_dict(processed: ProcessedItem) -> dict:
    """Serialise the LLM-produced, human-editable fields."""
    return {
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
        "areas": list(processed.areas),
        "data_protection_impact": processed.data_protection_impact,
        "it_landscape_impact": processed.it_landscape_impact,
        "config_change_required": processed.config_change_required,
        "kbv_change_required": processed.kbv_change_required,
    }


def item_from_source(s: dict) -> ChangeItem:
    return ChangeItem(
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
        release_date=_pdt(s.get("release_date")),
        act_by=_pdt(s.get("act_by")),
    )


def processed_from_edit(item: ChangeItem, e: dict) -> ProcessedItem:
    return ProcessedItem(
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
        areas=list(e.get("areas") or []),
        data_protection_impact=bool(e.get("data_protection_impact")),
        it_landscape_impact=bool(e.get("it_landscape_impact")),
        config_change_required=bool(e.get("config_change_required")),
        kbv_change_required=bool(e.get("kbv_change_required")),
        confluence_title=e.get("confluence_title", ""),
    )


def draft_from(item: ChangeItem, processed: ProcessedItem, make_page: bool) -> dict:
    return {
        "key": item.dedupe_key(),
        "source": source_dict(item),
        "edit": edit_dict(processed),
        "make_page": make_page,
        "ignored": False,
    }


def draft_to(draft: dict) -> tuple[ChangeItem, ProcessedItem, bool]:
    item = item_from_source(draft["source"])
    processed = processed_from_edit(item, draft["edit"])
    return item, processed, bool(draft.get("make_page", False))


def save_drafts(path: str | Path, drafts: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": drafts}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_drafts(path: str | Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw.get("items", [])
