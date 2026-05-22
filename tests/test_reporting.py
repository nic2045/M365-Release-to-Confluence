from m365_confluence.reporting import (
    build_dashboard_body,
    dashboard_title,
    group_by_quarter,
)
from m365_confluence.state import ItemState


def _state(key, quarter, slipped=False, title="Feature"):
    return ItemState(
        key=key,
        content_hash="h",
        title=title,
        confluence_title=f"[M365] {title}",
        status="In development",
        products=["Teams"],
        target_quarter=quarter,
        decision="Communicate",
        slipped=slipped,
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
