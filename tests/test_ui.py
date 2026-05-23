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
