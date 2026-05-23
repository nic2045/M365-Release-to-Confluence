from datetime import datetime, timezone

from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.review import draft_from, draft_to, load_drafts, save_drafts


def _pair():
    item = ChangeItem(
        id="MC1",
        source="message_center",
        title="Original",
        body="raw body",
        url="https://x",
        status="In development",
        products=["Teams"],
        tags=["MajorChange"],
        last_modified=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    processed = ProcessedItem(
        source_item=item,
        summary="sum",
        impact="imp",
        audience="Admins",
        action_items=["a", "b"],
        target_quarter="Q3 2026",
        decision="Communicate",
        decision_rationale="why",
        cab_required=True,
        cab_recommendation="CAB bitte",
        confluence_title="[M365] Original",
    )
    return item, processed


def test_draft_roundtrip_preserves_fields():
    item, processed = _pair()
    draft = draft_from(item, processed, make_page=True)
    item2, processed2, make_page = draft_to(draft)
    assert make_page is True
    assert item2.id == "MC1"
    assert item2.products == ["Teams"]
    assert item2.last_modified == item.last_modified
    assert processed2.summary == "sum"
    assert processed2.decision == "Communicate"
    assert processed2.cab_required is True
    assert processed2.action_items == ["a", "b"]
    assert processed2.confluence_title == "[M365] Original"


def test_save_and_load(tmp_path):
    item, processed = _pair()
    path = tmp_path / "review.json"
    save_drafts(path, [draft_from(item, processed, True)])
    drafts = load_drafts(path)
    assert len(drafts) == 1
    assert drafts[0]["edit"]["summary"] == "sum"


def test_edit_then_roundtrip():
    item, processed = _pair()
    draft = draft_from(item, processed, make_page=False)
    draft["edit"]["decision"] = "Deactivate"  # simulate human edit
    _, processed2, _ = draft_to(draft)
    assert processed2.decision == "Deactivate"


def test_draft_from_sets_ignored_false():
    item, processed = _pair()
    draft = draft_from(item, processed, make_page=True)
    assert draft["ignored"] is False


def test_draft_includes_services_and_map():
    from m365_confluence.models import ChangeItem, ProcessedItem

    item = ChangeItem(id="1", source="roadmap", title="t", body="b", products=["Outlook", "Teams"])
    draft = draft_from(
        item, ProcessedItem(source_item=item, summary="", impact="", audience=""), False
    )
    assert "Exchange Online" in draft["source"]["services"]
    assert draft["source"]["product_services"]["Outlook"] == "Exchange Online"
    assert draft["source"]["product_services"]["Teams"] == "Teams"
