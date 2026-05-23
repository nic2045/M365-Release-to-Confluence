import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from m365_confluence.ui.app import create_app  # noqa: E402


def _draft():
    return {
        "key": "roadmap:1",
        "source": {"id": "1", "source": "roadmap", "title": "T", "products": ["Teams"]},
        "edit": {
            "confluence_title": "[M365] T",
            "summary": "s",
            "decision": "Communicate",
            "cab_required": False,
            "target_quarter": "Q3 2026",
        },
        "make_page": False,
    }


def test_index_serves_html(tmp_path):
    client = TestClient(create_app(str(tmp_path / "review.json")))
    r = client.get("/")
    assert r.status_code == 200
    assert "M365 Review" in r.text


def test_drafts_empty_then_save_then_read(tmp_path):
    path = tmp_path / "review.json"
    client = TestClient(create_app(str(path)))

    assert client.get("/api/drafts").json()["items"] == []

    saved = client.post("/api/drafts", json={"items": [_draft()]})
    assert saved.json()["saved"] == 1

    items = client.get("/api/drafts").json()["items"]
    assert len(items) == 1
    assert items[0]["edit"]["summary"] == "s"


def test_publish_dry_run(tmp_path):
    path = tmp_path / "review.json"
    client = TestClient(create_app(str(path)))
    client.post("/api/drafts", json={"items": [_draft()]})
    r = client.post("/api/publish", json={"dry_run": True})
    assert r.status_code == 200
    assert r.json()["processed"] == 1


def test_publish_skips_ignored(tmp_path):
    path = tmp_path / "review.json"
    client = TestClient(create_app(str(path)))
    d1 = _draft()
    d2 = _draft()
    d2["key"] = "roadmap:2"
    d2["source"]["id"] = "2"
    d2["ignored"] = True
    client.post("/api/drafts", json={"items": [d1, d2]})
    r = client.post("/api/publish", json={"dry_run": True})
    assert r.json()["processed"] == 1  # ignored one excluded


def test_products_endpoint(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline

    monkeypatch.setattr(
        pipeline, "collect_products", lambda config: [("Teams", 3), ("Exchange", 1)]
    )
    client = TestClient(create_app(str(tmp_path / "review.json")))
    r = client.get("/api/products?source=roadmap")
    assert r.status_code == 200
    assert r.json()["products"][0] == {"name": "Teams", "count": 3}


def test_generate_endpoint(tmp_path, monkeypatch):
    import m365_confluence.pipeline as pipeline
    from m365_confluence.review import save_drafts

    path = tmp_path / "review.json"

    def fake_run(config, **kwargs):
        assert kwargs["review_out"] == str(path)
        save_drafts(str(path), [_draft()])
        return None

    monkeypatch.setattr(pipeline, "run", fake_run)
    client = TestClient(create_app(str(path)))
    r = client.post("/api/generate", json={"source": "roadmap", "limit": 5})
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_settings_roundtrip(tmp_path):
    client = TestClient(create_app(str(tmp_path / "review.json")))
    assert client.get("/api/settings").json() == {}
    payload = {"source": "both", "limit": 10, "products": ["Teams"], "worldwide_only": False}
    assert client.post("/api/settings", json=payload).json()["saved"] is True
    assert client.get("/api/settings").json() == payload
    assert (tmp_path / "ui_settings.json").exists()
