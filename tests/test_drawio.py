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


def test_timeline_rows_by_service():
    items = [_s("a", "x", "Outlook", "Q3 2026"), _s("b", "y", "Microsoft Teams", "Q3 2026")]
    xml = build_timeline(items, axis="quarter", rows="service")
    assert "Exchange Online" in xml
    assert "Teams" in xml


def test_timeline_is_wellformed_xml():
    import xml.etree.ElementTree as ET

    items = [
        _s(
            "a",
            'Title with <tag> & "quotes"',
            "Teams",
            "Q3 2026",
            decision="Deactivate",
            slipped=True,
        ),
        _s("b", "Outlook thing", "Outlook", "Q4 2026"),
    ]
    for axis in ("quarter", "month"):
        for rows in ("service", "product"):
            xml = build_timeline(items, axis=axis, rows=rows)
            ET.fromstring(xml)  # raises if not well-formed
    assert "<i>" not in build_timeline(items)  # markup is escaped in attributes


def test_fishbone_is_wellformed_and_has_spine():
    import xml.etree.ElementTree as ET

    items = [
        _s("a", "Outlook feat", "Outlook", "Q3 2026", decision="Communicate"),
        _s("b", "Teams feat", "Microsoft Teams", "Q3 2026", decision="Activate"),
        _s("c", "SP feat", "SharePoint", "Q4 2026", decision="Deactivate", slipped=True),
    ]
    xml = build_timeline(items, axis="quarter", style="fishbone")
    ET.fromstring(xml)  # well-formed
    assert 'edge="1"' in xml  # bones/spine are edges
    assert "Roadmap" in xml
    assert "Q3 2026" in xml
