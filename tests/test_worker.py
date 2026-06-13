from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from ariadne.rss import FeedItem
from ariadne.worker import (
    _analysis_exists,
    _default_feed_urls,
    _digest_schedule_hours,
    _digest_schedule_times,
    _filter_ingest_items,
    _next_digest_run,
    _positive_int,
    _rescheduled_ingest_payload,
    _should_skip_push,
    _should_reschedule_ingest,
    _successful_push_exists,
    upsert_raw_item,
)


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.row


class SequentialFakeConnection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.rows.pop(0)


def test_analysis_exists_returns_true_when_row_exists() -> None:
    conn = FakeConnection({"?column?": 1})

    assert _analysis_exists(conn, "item-1") is True
    assert conn.calls[0][1] == ("item-1",)


def test_successful_push_exists_returns_false_without_row() -> None:
    conn = FakeConnection(None)

    assert _successful_push_exists(conn, "item-1") is False
    assert conn.calls[0][1] == ("item-1",)


def test_should_skip_push_when_successful_push_exists() -> None:
    conn = FakeConnection({"?column?": 1})

    assert _should_skip_push(conn, "item-1", {}) is True


def test_should_not_skip_push_when_force_is_true() -> None:
    conn = FakeConnection({"?column?": 1})

    assert _should_skip_push(conn, "item-1", {"force": True}) is False


def test_should_reschedule_ingest_for_configured_default_feeds() -> None:
    assert _should_reschedule_ingest({}) is True


def test_should_not_reschedule_ad_hoc_feed_urls_by_default() -> None:
    assert _should_reschedule_ingest({"feed_urls": ["https://hnrss.org/frontpage"]}) is False


def test_should_reschedule_when_repeat_is_explicit() -> None:
    assert _should_reschedule_ingest({"feed_urls": ["https://hnrss.org/frontpage"], "repeat": True}) is True


def test_default_feed_urls_skips_freshrss_output_when_api_is_enabled() -> None:
    settings = SimpleNamespace(
        rss_urls=["https://example.com/rss.xml"],
        freshrss_urls=["http://freshrss/i/?a=rss"],
        feed_urls=["https://example.com/rss.xml", "http://freshrss/i/?a=rss"],
    )

    assert _default_feed_urls(settings, use_freshrss_api=True) == ["https://example.com/rss.xml"]
    assert _default_feed_urls(settings, use_freshrss_api=False) == [
        "https://example.com/rss.xml",
        "http://freshrss/i/?a=rss",
    ]


def test_rescheduled_default_ingest_keeps_default_source_selection() -> None:
    assert _rescheduled_ingest_payload({}, []) == {"repeat": True}


def test_rescheduled_ad_hoc_ingest_keeps_explicit_feed_urls() -> None:
    assert _rescheduled_ingest_payload({"feed_urls": ["https://hnrss.org/frontpage"]}, ["https://hnrss.org/frontpage"]) == {
        "feed_urls": ["https://hnrss.org/frontpage"],
        "repeat": True,
    }


def test_digest_schedule_hours_parses_and_sorts_values() -> None:
    assert _digest_schedule_hours("17, 9, bad, 99") == [9, 17]
    assert _digest_schedule_hours("bad") == [9, 17]


def test_digest_schedule_times_parses_sorts_and_deduplicates_values() -> None:
    assert _digest_schedule_times("17:30, 09:00, bad, 99:00, 9:00") == [(9, 0), (17, 30)]


def test_digest_schedule_times_falls_back_to_hours() -> None:
    assert _digest_schedule_times("bad", "8, 20") == [(8, 0), (20, 0)]


def test_next_digest_run_uses_same_day_when_future_slot_exists() -> None:
    now = datetime(2026, 6, 13, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _next_digest_run(now, [(9, 15), (17, 0)]) == datetime(
        2026,
        6,
        13,
        9,
        15,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )


def test_next_digest_run_rolls_to_next_day_after_last_slot() -> None:
    now = datetime(2026, 6, 13, 17, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert _next_digest_run(now, [(9, 30), (17, 15)]) == datetime(
        2026,
        6,
        14,
        9,
        30,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )


def test_filter_ingest_items_skips_old_items_and_keeps_missing_dates() -> None:
    settings = SimpleNamespace(ingest_max_items_per_feed=10, ingest_max_item_age_days=7)
    recent = _feed_item("recent", datetime.now(timezone.utc) - timedelta(days=1))
    old = _feed_item("old", datetime.now(timezone.utc) - timedelta(days=30))
    undated = _feed_item("undated", None)

    filtered = _filter_ingest_items([recent, old, undated], {}, settings)

    assert [item.title for item in filtered] == ["recent", "undated"]


def test_filter_ingest_items_limits_per_feed_before_date_filter() -> None:
    settings = SimpleNamespace(ingest_max_items_per_feed=2, ingest_max_item_age_days=7)
    items = [
        _feed_item("one", datetime.now(timezone.utc)),
        _feed_item("two", datetime.now(timezone.utc)),
        _feed_item("three", datetime.now(timezone.utc)),
    ]

    filtered = _filter_ingest_items(items, {}, settings)

    assert [item.title for item in filtered] == ["one", "two"]


def test_positive_int_uses_default_for_invalid_values() -> None:
    assert _positive_int("3", 7) == 3
    assert _positive_int("0", 7) == 7
    assert _positive_int("bad", 7) == 7


def test_upsert_raw_item_marks_new_item_for_normalization() -> None:
    conn = SequentialFakeConnection([{"id": "source-1"}, None, {"id": "raw-1"}])

    raw_item_id, created = upsert_raw_item(conn, _feed_item("one", datetime.now(timezone.utc)))

    assert raw_item_id == "raw-1"
    assert created is True


def test_upsert_raw_item_skips_normalization_for_existing_item() -> None:
    conn = SequentialFakeConnection([{"id": "source-1"}, {"id": "raw-1"}, {"id": "raw-1"}])

    raw_item_id, created = upsert_raw_item(conn, _feed_item("one", datetime.now(timezone.utc)))

    assert raw_item_id == "raw-1"
    assert created is False


def _feed_item(title: str, published_at: datetime | None) -> FeedItem:
    return FeedItem(
        source_name="Example",
        source_url="https://example.com/feed",
        external_id=title,
        url=f"https://example.com/{title}",
        title=title,
        author=None,
        published_at=published_at,
        content=title,
        raw_payload={},
    )
