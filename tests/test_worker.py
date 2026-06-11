from ariadne.worker import _analysis_exists, _should_skip_push, _should_reschedule_ingest, _successful_push_exists


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.row


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
