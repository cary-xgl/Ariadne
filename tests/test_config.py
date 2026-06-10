from ariadne.config import Settings


def test_feed_urls_merge_plain_rss_and_freshrss_urls() -> None:
    settings = Settings(
        rss_feed_urls="https://example.com/rss.xml, https://example.com/atom.xml",
        freshrss_feed_urls="http://localhost:8080/i/?a=rss&user=ariadne",
    )

    assert settings.feed_urls == [
        "https://example.com/rss.xml",
        "https://example.com/atom.xml",
        "http://localhost:8080/i/?a=rss&user=ariadne",
    ]
