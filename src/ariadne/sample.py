from __future__ import annotations

from datetime import datetime, timezone

from ariadne.rss import FeedItem


def sample_feed_items() -> list[FeedItem]:
    return [
        FeedItem(
            source_name="Ariadne Sample Feed",
            source_url="ariadne://sample-feed",
            external_id="sample-python-docker-ai-workflow",
            url="https://example.com/ariadne/sample-python-docker-ai-workflow",
            title="Python Docker AI workflow reaches first local milestone",
            author="Ariadne",
            published_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
            content=(
                "A local information-flow pipeline now uses Python, Docker, "
                "Postgres, and an AI model analysis step to normalize, score, "
                "and dry-run push a useful item."
            ),
            raw_payload={"fixture": "sample-feed-v1"},
        )
    ]
