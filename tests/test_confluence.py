from m365_confluence.config import ConfluenceConfig
from m365_confluence.confluence.client import ConfluenceClient


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, existing=None):
        self.headers = {}
        self._existing = existing
        self.posted = None
        self.put_url = None

    def get(self, url, params=None, timeout=None):
        results = [self._existing] if self._existing else []
        return _Resp({"results": results})

    def post(self, url, json=None, timeout=None):
        self.posted = json
        return _Resp({"id": "new", **json})

    def put(self, url, json=None, timeout=None):
        self.put_url = url
        return _Resp({"id": "existing", **json})


def _config():
    return ConfluenceConfig(
        base_url="https://confluence.example.com",
        token="tok",
        space_key="OPS",
        parent_page_id="42",
    )


def test_create_when_missing():
    session = _FakeSession(existing=None)
    client = ConfluenceClient(_config(), session=session)
    client.upsert_page("Title", "<p>body</p>")
    assert session.posted["title"] == "Title"
    assert session.posted["ancestors"] == [{"id": "42"}]
    assert session.headers["Authorization"] == "Bearer tok"


def test_update_when_present():
    existing = {"id": "777", "version": {"number": 3}}
    session = _FakeSession(existing=existing)
    client = ConfluenceClient(_config(), session=session)
    result = client.upsert_page("Title", "<p>body</p>")
    assert session.put_url.endswith("/777")
    assert result["version"]["number"] == 4
