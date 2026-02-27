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


def test_dashboard_map_latest_query_enforces_scope_and_priority_ordering():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_map_latest(as_of=date(2026, 2, 19), limit=50)

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "PARTITION BY o.region_code, o.office_type, o.audience_scope" in query
    assert "COALESCE(o.legal_completeness_score, 0.0) DESC" in query
    assert "THEN 3" in query
    assert "scoped_rank AS" in query
    assert "WHERE r.scope_rn = 1" in query
    assert params == [date(2026, 2, 19), 50]
