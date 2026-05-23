from m365_confluence.drawio import build_timeline
from m365_confluence.state import ItemState


def _s(key, title, product, quarter, decision="Communicate", slipped=False):
    return ItemState(
        key=key,
        content_hash="h",
        title=title,
        products=[product],
        target_quarter=quarter,
        decision=decision,
        slipped=slipped,
    )


def test_timeline_quarter_axis_has_structure():
    xml = build_timeline([_s("a", "Teams thing", "Teams", "Q3 2026")], axis="quarter")
    assert xml.startswith("<mxfile>")
    assert "mxGraphModel" in xml
    assert "Teams" in xml
    assert "Q3 2026" in xml
    assert "Teams thing" in xml


def test_timeline_month_axis_expands_months():
    items = [
        _s("a", "early", "Teams", "Q1 2026"),
        _s("b", "late", "Teams", "Q2 2026"),
    ]
    xml = build_timeline(items, axis="month")
    # Q1->Jan, Q2->Apr; the continuous axis includes the months between.
    for label in ("Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026"):
        assert label in xml


def test_timeline_groups_products_and_unscheduled():
    items = [
        _s("a", "x", "Exchange", "Q3 2026"),
        _s("b", "y", "SharePoint", ""),  # no quarter -> Unscheduled
    ]
    xml = build_timeline(items, axis="quarter")
    assert "Exchange" in xml
    assert "SharePoint" in xml
    assert "Unscheduled" in xml


def test_timeline_decision_colour():
    xml = build_timeline([_s("a", "x", "Teams", "Q3 2026", decision="Deactivate")], axis="quarter")
    assert "#fde0e0" in xml  # Deactivate fill
