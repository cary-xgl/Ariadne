from ariadne.worker import _format_push_message


def test_format_push_message_strips_html_from_summary() -> None:
    message = _format_push_message(
        {
            "title": "Example Item",
            "summary": '<p>Article URL: <a href="https://example.com/item">https://example.com/item</a></p>',
            "reason": "No strong topic match; keep for digest review.",
            "source_name": "Example Feed",
            "importance_score": 0.42,
            "canonical_url": "https://example.com/item",
        }
    )

    assert message["msg_type"] == "interactive"
    assert message["card"]["header"]["title"]["content"] == "Example Item"
    card_text = str(message["card"])
    assert "<p>" not in card_text
    assert "<a href=" not in card_text
    assert "Article URL: https://example.com/item" in card_text
    assert "Example Feed" in card_text
    assert message["card"]["elements"][-1]["actions"][0]["url"] == "https://example.com/item"
