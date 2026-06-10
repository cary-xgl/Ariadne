from ariadne.analysis import analyze_item
from ariadne.sample import sample_feed_items


def test_sample_feed_item_is_stable_and_analyzable() -> None:
    items = sample_feed_items()

    assert len(items) == 1
    assert items[0].external_id == "sample-python-docker-ai-workflow"
    assert items[0].source_url == "ariadne://sample-feed"

    result = analyze_item(items[0].title, items[0].content)
    assert "engineering" in result.topics
    assert "ai" in result.topics
    assert result.recommended_action == "read_now"
