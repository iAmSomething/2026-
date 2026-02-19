from datetime import date

from app.services.repository import PostgresRepository


class _RecordingCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple[str, list | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows


class _RecordingConn:
    def __init__(self, rows):
        self._cursor = _RecordingCursor(rows)

    def cursor(self):
        return self._cursor


def test_dashboard_summary_query_filters_regional_scope():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=date(2026, 2, 19))

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    scope_filter = "(o.audience_scope = 'national' OR o.audience_scope IS NULL)"
    assert query.count(scope_filter) >= 2
    assert params == [date(2026, 2, 19)]


def test_dashboard_summary_query_filters_scope_without_as_of():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=None)

    query, params = conn._cursor.executed[0]
    assert "(o.audience_scope = 'national' OR o.audience_scope IS NULL)" in query
    assert params == []
