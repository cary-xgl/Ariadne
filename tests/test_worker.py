from ariadne.worker import _analysis_exists, _successful_push_exists


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
