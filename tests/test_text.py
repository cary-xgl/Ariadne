from ariadne.text import canonicalize_url, normalize_text, sha256_text, slugify


def test_canonicalize_url_removes_tracking_params() -> None:
    assert (
        canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2&fbclid=y&a=1#frag")
        == "https://example.com/a?a=1&b=2"
    )


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text(" hello\n\n world\t ") == "hello world"


def test_sha256_text_is_stable() -> None:
    assert sha256_text("ariadne") == sha256_text("ariadne")


def test_slugify_keeps_ascii_and_cjk() -> None:
    assert slugify("Hello Ariadne 信息流!") == "hello-ariadne-信息流"
