from ariadne.worker import _digest_limit, _format_digest_message, _format_push_message


def test_format_push_message_strips_html_and_bare_urls_from_summary() -> None:
    message = _format_push_message(
        {
            "title": "Example Item",
            "summary": (
                '<p>Article URL: <a href="https://example.com/item/very/long/path">'
                "https://example.com/item/very/long/path</a></p>"
            ),
            "reason": "No strong topic match; keep for digest review.",
            "source_name": "Example Feed",
            "importance_score": 0.42,
            "canonical_url": "https://example.com/item/very/long/path",
        }
    )

    assert message["msg_type"] == "interactive"
    assert message["card"]["header"]["title"]["content"] == "Example Item"
    card_text = str(message["card"])
    summary_text = message["card"]["elements"][0]["text"]["content"]
    assert "<p>" not in card_text
    assert "<a href=" not in card_text
    assert "Article URL:" not in summary_text
    assert "https://example.com/item/very/long/path" not in summary_text
    assert "Example Feed" in card_text
    assert message["card"]["elements"][-1]["actions"][0]["url"] == "https://example.com/item/very/long/path"


def test_format_digest_message_contains_multiple_items() -> None:
    message = _format_digest_message(
        [
            {
                "title": "First Item",
                "summary": "<p>Article URL: https://example.com/first/very/long/path First summary</p>",
                "source_name": "Feed A",
                "importance_score": 0.8,
                "canonical_url": "https://example.com/first/very/long/path",
            },
            {
                "title": "Second Item",
                "summary": "Second summary",
                "source_name": "Feed B",
                "importance_score": 0.4,
                "canonical_url": "https://example.com/second",
            },
        ]
    )

    assert message["msg_type"] == "interactive"
    assert message["card"]["header"]["title"]["content"] == "Ariadne 信息流摘要"
    card_text = str(message["card"])
    assert "<p>" not in card_text
    assert "First summary" in card_text
    assert "Article URL:" not in card_text
    assert "https://example.com/first/very/long/path" in card_text
    assert "Second Item" in card_text


def test_digest_limit_is_clamped() -> None:
    assert _digest_limit("bad") == 10
    assert _digest_limit(0) == 1
    assert _digest_limit(99) == 20
