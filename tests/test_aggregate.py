from datetime import datetime, timedelta, timezone

from m365_confluence.models import ChangeItem
from m365_confluence.sources.aggregate import aggregate

NOW = datetime.now(timezone.utc)


def _item(source: str, id_: str, days_ago: int) -> ChangeItem:
    return ChangeItem(
        id=id_,
        source=source,
        title=f"{source}-{id_}",
        body="x",
        last_modified=NOW - timedelta(days=days_ago),
    )


def test_dedupes_by_source_and_id():
    a = [_item("roadmap", "1", 1), _item("roadmap", "1", 1)]
    assert len(aggregate([a])) == 1


def test_keeps_same_id_across_sources():
    merged = aggregate([[_item("roadmap", "1", 1)], [_item("message_center", "1", 1)]])
    assert len(merged) == 2


def test_sorts_newest_first():
    merged = aggregate([[_item("roadmap", "old", 10), _item("roadmap", "new", 1)]])
    assert [i.id for i in merged] == ["new", "old"]


def test_since_filters_old_items():
    merged = aggregate(
        [[_item("roadmap", "old", 30), _item("roadmap", "new", 1)]], since=NOW - timedelta(days=7)
    )
    assert [i.id for i in merged] == ["new"]


def test_limit_caps_results():
    items = [_item("roadmap", str(n), n) for n in range(5)]
    assert len(aggregate([items], limit=2)) == 2
