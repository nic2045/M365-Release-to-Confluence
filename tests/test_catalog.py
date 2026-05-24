from datetime import datetime, timezone

from m365_confluence.catalog import (
    Catalog,
    debug_rows,
    enrich_catalog,
    publish_catalog,
    sync_catalog,
)
from m365_confluence.models import ChangeItem, ProcessedItem


class _Cfg:
    """Minimal stand-in for Config: catalog code only touches .ai here."""

    class _AI:
        output_language = "de"
        org_context = ""

    def __init__(self):
        self.ai = self._AI()


def _item(id="1", title="T", body="raw", products=None, status="Launched"):
    return ChangeItem(
        id=id,
        source="roadmap",
        title=title,
        body=body,
        products=products or ["Teams"],
        status=status,
        last_modified=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def test_sync_flags_new_then_unchanged_then_changed(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline

    path = str(tmp_path / "cat.json")
    cfg = _Cfg()

    monkeypatch.setattr(pipeline, "collect", lambda config: [[_item(title="A")]])
    r1 = sync_catalog(cfg, catalog_file=path)
    assert (r1.total, r1.new, r1.changed, r1.unchanged) == (1, 1, 0, 0)

    # Same content -> unchanged.
    r2 = sync_catalog(cfg, catalog_file=path)
    assert (r2.new, r2.changed, r2.unchanged) == (0, 0, 1)

    # Changed body -> changed.
    monkeypatch.setattr(pipeline, "collect", lambda config: [[_item(title="A2", body="new")]])
    r3 = sync_catalog(cfg, catalog_file=path)
    assert (r3.new, r3.changed) == (0, 1)

    # Gone next sync -> removed.
    monkeypatch.setattr(pipeline, "collect", lambda config: [[]])
    r4 = sync_catalog(cfg, catalog_file=path)
    assert r4.removed == 1


def test_sync_labels_service_and_quarter(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline

    path = str(tmp_path / "cat.json")
    monkeypatch.setattr(pipeline, "collect", lambda config: [[_item(products=["Outlook"])]])
    sync_catalog(_Cfg(), catalog_file=path)
    cat = Catalog(path).load()
    entry = next(iter(cat.items.values()))
    assert "Exchange Online" in entry["source"]["services"]
    assert entry["enriched"] is False


def test_enrich_only_runs_for_selected_and_caches(tmp_path, monkeypatch):
    import m365_confluence.catalog as catmod
    import m365_confluence.pipeline as pipeline

    path = str(tmp_path / "cat.json")
    monkeypatch.setattr(
        pipeline,
        "collect",
        lambda config: [[_item(id="1"), _item(id="2", title="Second")]],
    )
    sync_catalog(_Cfg(), catalog_file=path)

    calls = []

    def fake_process(provider, item, language, org):
        calls.append(item.id)
        return ProcessedItem(
            source_item=item,
            summary="s",
            impact="i",
            audience="a",
            decision="Communicate",
            confluence_title=item.title,
        )

    monkeypatch.setattr(catmod, "process_item", fake_process)
    monkeypatch.setattr(catmod, "build_provider", lambda ai: object())

    r = enrich_catalog(_Cfg(), ["roadmap:1"], catalog_file=path)
    assert r.enriched == 1 and calls == ["1"]

    cat = Catalog(path).load()
    assert cat.items["roadmap:1"]["enriched"] is True
    assert cat.items["roadmap:1"]["edit"]["summary"] == "s"
    assert cat.items["roadmap:2"]["enriched"] is False

    # Re-enrich without force is skipped (cached).
    calls.clear()
    r2 = enrich_catalog(_Cfg(), ["roadmap:1"], catalog_file=path)
    assert r2.skipped == 1 and calls == []


def test_publish_catalog_only_enriched_non_ignored(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline

    path = str(tmp_path / "cat.json")
    monkeypatch.setattr(pipeline, "collect", lambda config: [[_item(id="1")]])
    sync_catalog(_Cfg(), catalog_file=path)

    captured = {}

    def fake_publish_drafts(config, drafts, **kwargs):
        captured["drafts"] = drafts
        from m365_confluence.pipeline import RunResult

        return RunResult(
            fetched=len(drafts),
            processed=len(drafts),
            published=len(drafts),
            skipped=0,
            unchanged=0,
            slipped=0,
            new=0,
            changed=0,
            dashboards=0,
        )

    monkeypatch.setattr(pipeline, "publish_drafts", fake_publish_drafts)

    # Not enriched yet -> nothing to publish.
    publish_catalog(_Cfg(), catalog_file=path, dry_run=True)
    assert captured["drafts"] == []

    # Enrich, then it becomes publishable and gets stamped.
    cat = Catalog(path).load()
    cat.items["roadmap:1"]["enriched"] = True
    cat.items["roadmap:1"]["edit"] = {"confluence_title": "T", "summary": "s"}
    cat.save()
    publish_catalog(_Cfg(), catalog_file=path, dry_run=False)
    assert len(captured["drafts"]) == 1
    cat2 = Catalog(path).load()
    assert cat2.items["roadmap:1"]["published"] is True
    assert cat2.items["roadmap:1"]["published_at"]


def test_debug_rows(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline

    path = str(tmp_path / "cat.json")
    monkeypatch.setattr(pipeline, "collect", lambda config: [[_item()]])
    sync_catalog(_Cfg(), catalog_file=path)
    rows = debug_rows(Catalog(path).load())
    assert len(rows) == 1
    assert rows[0]["change_status"] == "new"
    assert rows[0]["published"] is False
    assert rows[0]["first_seen"]
