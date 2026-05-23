from m365_confluence.reporting import (
    build_dashboard_body,
    dashboard_title,
    group_by_quarter,
    quarter_dashboards,
)
from m365_confluence.state import ItemState


def _state(
    key,
    quarter,
    slipped=False,
    title="Feature",
    has_page=True,
    summary="A summary",
    previous_quarter="",
    quarter_history=None,
):
    return ItemState(
        key=key,
        content_hash="h",
        title=title,
        confluence_title=f"[M365] {title}",
        status="In development",
        products=["Teams"],
        target_quarter=quarter,
        decision="Communicate",
        summary=summary,
        has_page=has_page,
        slipped=slipped,
        previous_quarter=previous_quarter,
        quarter_history=quarter_history or [],
    )


def test_dashboard_title_uses_unscheduled():
    assert dashboard_title("Q3 2026", "[M365] ") == "[M365] Rollouts Q3 2026"
    assert dashboard_title("", "[M365] ") == "[M365] Rollouts Unscheduled"


def test_group_by_quarter_sorts_and_buckets_unknown():
    groups = group_by_quarter([_state("a", "Q2 2026"), _state("b", "Q1 2026"), _state("c", "")])
    assert list(groups.keys()) == ["Q1 2026", "Q2 2026", "Unscheduled"]


def test_dashboard_body_links_and_flags_slip():
    body = build_dashboard_body("Q3 2026", [_state("a", "Q3 2026", slipped=True)])
    assert 'ri:content-title="[M365] Feature"' in body
    assert "verschoben" in body
    assert "Q3 2026" in body
    assert "A summary" in body  # description column


def test_dashboard_no_link_without_page():
    body = build_dashboard_body("Q3 2026", [_state("a", "Q3 2026", has_page=False)])
    assert "ri:content-title" not in body
    assert "<strong>Feature</strong>" in body


def test_quarter_dashboards_show_moved_out_in_old_quarter():
    moved = _state(
        "a", "Q4 2026", slipped=True, previous_quarter="Q3 2026", quarter_history=["Q3 2026"]
    )
    dashboards = dict(quarter_dashboards([moved]))
    # Old quarter exists and mentions the move
    assert "Q3 2026" in dashboards
    assert "Aus diesem Quartal verschoben" in dashboards["Q3 2026"]
    assert "verschoben nach Q4 2026" in dashboards["Q3 2026"]
    # New quarter shows the item with "aus Q3 2026"
    assert "verschoben aus Q3 2026" in dashboards["Q4 2026"]


def test_dashboard_groups_by_product_with_headings():
    a = _state("a", "Q3 2026", title="Teams Feature")
    b = _state("b", "Q3 2026", title="SP Feature")
    b.products = ["SharePoint"]
    a.products = ["Microsoft Teams"]
    a.cab_recommendation = "CAB-Review empfohlen"
    body = build_dashboard_body("Q3 2026", [a, b])
    assert "<h3>Microsoft Teams</h3>" in body
    assert "<h3>SharePoint</h3>" in body
    assert "CAB-Empfehlung" in body  # header
    assert "CAB-Review empfohlen" in body  # value


def test_dashboard_no_product_bucket():
    s = _state("a", "Q3 2026")
    s.products = []
    body = build_dashboard_body("Q3 2026", [s])
    assert "<h3>Ohne Produkt</h3>" in body


def test_feature_appears_under_each_product():
    s = _state("a", "Q3 2026", title="Multi")
    s.products = ["Teams", "Exchange"]
    body = build_dashboard_body("Q3 2026", [s])
    assert "<h3>Teams</h3>" in body
    assert "<h3>Exchange</h3>" in body


def test_cab_badge_in_dashboard():
    s = _state("a", "Q3 2026")
    s.cab_required = True
    s.cab_recommendation = "Bitte CAB prüfen"
    body = build_dashboard_body("Q3 2026", [s])
    assert "CAB: Ja" in body
    assert "Bitte CAB" in body
