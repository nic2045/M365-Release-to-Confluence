from datetime import datetime, timezone

from m365_confluence.filters import apply_filters
from m365_confluence.models import ChangeItem


def _item(id_, *, tags=None, act_by=None, products=None, category=""):
    return ChangeItem(
        id=id_,
        source="message_center",
        title="t",
        body="b",
        category=category,
        tags=tags or [],
        products=products or [],
        act_by=act_by,
    )


def test_no_filters_passes_all():
    items = [_item("1"), _item("2")]
    assert len(apply_filters(items)) == 2


def test_major_only():
    items = [_item("1", tags=["MajorChange"]), _item("2")]
    assert [i.id for i in apply_filters(items, major_only=True)] == ["1"]


def test_action_required():
    items = [_item("1", act_by=datetime(2026, 6, 1, tzinfo=timezone.utc)), _item("2")]
    assert [i.id for i in apply_filters(items, action_required=True)] == ["1"]


def test_product_substring_case_insensitive():
    items = [_item("1", products=["Microsoft Teams"]), _item("2", products=["Exchange"])]
    assert [i.id for i in apply_filters(items, products=["teams"])] == ["1"]


def test_category_filter():
    items = [_item("1", category="planForChange"), _item("2", category="stayInformed")]
    assert [i.id for i in apply_filters(items, categories=["planforchange"])] == ["1"]


def test_filters_combine_with_and():
    items = [
        _item("1", tags=["MajorChange"], products=["Teams"]),
        _item("2", tags=["MajorChange"], products=["Exchange"]),
    ]
    result = apply_filters(items, major_only=True, products=["teams"])
    assert [i.id for i in result] == ["1"]
