from datetime import datetime, timezone

from m365_confluence.models import ChangeItem, ProcessedItem
from m365_confluence.state import StateStore, content_hash


def _item(body: str = "v1") -> ChangeItem:
    return ChangeItem(
        id="MC1",
        source="message_center",
        title="T",
        body=body,
        status="In development",
        last_modified=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _processed(item: ChangeItem, quarter: str) -> ProcessedItem:
    return ProcessedItem(
        source_item=item,
        summary="s",
        impact="i",
        audience="Admins",
        target_quarter=quarter,
        decision="Communicate",
        confluence_title="[M365] T",
    )


def test_content_hash_changes_with_body():
    assert content_hash(_item("v1")) != content_hash(_item("v2"))


def test_roundtrip_and_unchanged(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    item = _item()
    assert store.is_unchanged(item) is False  # unknown item
    store.record(item, _processed(item, "Q3 2026"))
    store.save()

    reloaded = StateStore(path).load()
    assert reloaded.is_unchanged(item) is True
    assert reloaded.is_unchanged(_item("changed")) is False
    assert reloaded.get(item.dedupe_key()).target_quarter == "Q3 2026"


def test_injected_backend_roundtrip():
    """A custom (e.g. DB-backed) backend is used instead of a file."""
    store: dict = {}

    class MemBackend:
        def read(self):
            return dict(store)

        def write(self, payload):
            store.clear()
            store.update(payload)

    s = StateStore(backend=MemBackend())
    item = _item()
    s.record(item, _processed(item, "Q3 2026"))
    s.save()
    assert "items" in store and item.dedupe_key() in store["items"]

    reloaded = StateStore(backend=MemBackend()).load()
    assert reloaded.is_unchanged(item) is True


def test_requires_path_or_backend():
    import pytest

    with pytest.raises(ValueError):
        StateStore()


def test_all_items(tmp_path):
    store = StateStore(tmp_path / "s.json")
    item = _item()
    store.record(item, _processed(item, "Q3 2026"))
    items = store.all_items()
    assert len(items) == 1
    assert items[0].decision == "Communicate"
