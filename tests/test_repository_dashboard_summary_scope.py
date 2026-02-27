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


def test_dashboard_summary_query_uses_priority_tiebreak_within_scope():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=date(2026, 2, 19))

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "PARTITION BY po.option_type, po.option_name, o.audience_scope" in query
    assert "CASE UPPER(COALESCE(o.source_grade, ''))" in query
    assert "COALESCE(o.official_release_at, a.published_at) DESC NULLS LAST" in query
    assert "o.updated_at DESC NULLS LAST" in query
    assert "'nesdc' = ANY(COALESCE(o.source_channels, ARRAY[]::text[]))" in query
    assert "AND rl.option_name = po.option_name" in query
    assert "rl.audience_scope IS NOT DISTINCT FROM o.audience_scope" in query
    assert "AND rl.rn = 1" in query
    assert params == [date(2026, 2, 19)]


def test_dashboard_summary_query_no_hardcoded_national_filter_without_as_of():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=None)

    query, params = conn._cursor.executed[0]
    assert "o.audience_scope = 'national'" not in query
    assert "IS NOT DISTINCT FROM o.audience_scope" in query
    assert "ROW_NUMBER() OVER" in query
    assert params == []
