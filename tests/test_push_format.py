from ariadne.worker import _format_push_message


def test_format_push_message_strips_html_from_summary() -> None:
    message = _format_push_message(
        {
            "title": "Example Item",
            "summary": '<p>Article URL: <a href="https://example.com/item">https://example.com/item</a></p>',
            "reason": "No strong topic match; keep for digest review.",
            "canonical_url": "https://example.com/item",
        }
    )

    text = message["content"]["text"]
    assert "<p>" not in text
    assert "<a href=" not in text
    assert "Article URL: https://example.com/item" in text
