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
    assert settings.rss_urls == ["https://example.com/rss.xml", "https://example.com/atom.xml"]
    assert settings.freshrss_urls == ["http://localhost:8080/i/?a=rss&user=ariadne"]


def test_freshrss_api_configured_requires_base_url_username_and_password() -> None:
    assert Settings(
        _env_file=None,
        freshrss_api_base_url="http://freshrss/api/greader.php",
        freshrss_api_username="user",
        freshrss_api_password="api-password",
    ).freshrss_api_configured is True
    assert Settings(_env_file=None, freshrss_api_base_url="http://freshrss/api/greader.php").freshrss_api_configured is False


def test_default_ingest_interval_is_four_hours() -> None:
    assert Settings(_env_file=None).ingest_interval_seconds == 14400
