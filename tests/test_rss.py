from ariadne import rss
from ariadne.rss import fetch_feed, parse_feed


def test_parse_rss_description_strips_html() -> None:
    body = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>Example Item</title>
      <link>https://example.com/item</link>
      <guid>example-item</guid>
      <description><![CDATA[<p>Article URL: <a href="https://example.com/item">https://example.com/item</a></p>]]></description>
    </item>
  </channel>
</rss>
"""

    items = parse_feed(body, "https://example.com/rss")

    assert len(items) == 1
    assert items[0].content == "Article URL: https://example.com/item"


def test_fetch_feed_sends_custom_headers(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Example</title></channel></rss>"""

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(rss.urllib.request, "urlopen", fake_urlopen)

    fetch_feed("https://example.com/rss", timeout=7, headers={"Authorization": "Bearer token"})

    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["headers"]["User-agent"] == "Ariadne/0.1"
    assert captured["timeout"] == 7
