import json

from ariadne import freshrss_api
from ariadne.freshrss_api import fetch_freshrss_items


def test_fetch_freshrss_items_logs_in_and_reads_reading_list(monkeypatch) -> None:
    requests = []

    class FakeResponse:
        def __init__(self, body: bytes):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return self.body

    def fake_urlopen(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/accounts/ClientLogin"):
            return FakeResponse(b"SID=sid\nLSID=lsid\nAuth=secret-token\n")
        assert request.full_url.endswith("/reader/api/0/stream/contents/reading-list?n=20")
        body = {
            "items": [
                {
                    "id": "item-1",
                    "title": "Example",
                    "author": "Ada",
                    "published": 1781366400,
                    "canonical": [{"href": "https://example.com/article"}],
                    "summary": {"content": "<p>Hello <strong>world</strong></p>"},
                    "origin": {"title": "Example Feed"},
                }
            ]
        }
        return FakeResponse(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(freshrss_api.urllib.request, "urlopen", fake_urlopen)

    items = fetch_freshrss_items("http://freshrss/api/greader.php/", "user", "api-password", limit=20)

    assert len(items) == 1
    assert items[0].source_name == "Example Feed"
    assert items[0].url == "https://example.com/article"
    assert items[0].title == "Example"
    assert items[0].author == "Ada"
    assert items[0].content == "Hello world"
    assert dict(requests[1].header_items())["Authorization"] == "GoogleLogin auth=secret-token"
