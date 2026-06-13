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


def test_rss_request_headers_build_basic_auth() -> None:
    settings = Settings(rss_auth_username="user", rss_auth_password="secret")

    assert settings.rss_request_headers == {"Authorization": "Basic dXNlcjpzZWNyZXQ="}


def test_rss_request_headers_prefer_bearer_token() -> None:
    settings = Settings(
        rss_auth_username="user",
        rss_auth_password="secret",
        rss_auth_bearer_token="token",
    )

    assert settings.rss_request_headers == {"Authorization": "Bearer token"}


def test_rss_request_headers_parse_extra_headers() -> None:
    settings = Settings(rss_extra_headers='{"X-Api-Key":"secret","X-Feed":"fresh"}')

    assert settings.rss_request_headers == {"X-Api-Key": "secret", "X-Feed": "fresh"}


def test_rss_request_headers_parse_semicolon_headers() -> None:
    settings = Settings(rss_extra_headers="X-Api-Key: secret; X-Feed: fresh")

    assert settings.rss_request_headers == {"X-Api-Key": "secret", "X-Feed": "fresh"}


def test_freshrss_api_configured_requires_base_url_username_and_password() -> None:
    assert Settings(
        freshrss_api_base_url="http://freshrss/api/greader.php",
        freshrss_api_username="user",
        freshrss_api_password="api-password",
    ).freshrss_api_configured is True
    assert Settings(freshrss_api_base_url="http://freshrss/api/greader.php").freshrss_api_configured is False
