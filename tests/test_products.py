from datetime import datetime, timezone

import m365_confluence.pipeline as pipeline
from m365_confluence.models import ChangeItem


def _item(id_, products, days):
    return ChangeItem(
        id=id_,
        source="roadmap",
        title="t",
        body="b",
        products=products,
        last_modified=datetime(2026, 5, days, tzinfo=timezone.utc),
    )


def test_collect_products_counts_and_orders(monkeypatch):
    items = [
        _item("1", ["Teams", "Exchange"], 1),
        _item("2", ["Teams"], 2),
        _item("3", ["SharePoint"], 3),
    ]
    monkeypatch.setattr(pipeline, "collect", lambda config: [items])
    result = pipeline.collect_products(config=None)
    assert result[0] == ("Teams", 2)  # most common first
    assert ("Exchange", 1) in result
    assert ("SharePoint", 1) in result
    assert len(result) == 3
