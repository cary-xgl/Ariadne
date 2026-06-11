from ariadne.rss import parse_feed


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
