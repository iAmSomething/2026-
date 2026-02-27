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


def test_fetch_trends_query_for_national_scope_does_not_add_region_filter():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_trends(metric="party_support", scope="national", region_code=None, days=30)

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "po.option_type = %s" in query
    assert "o.audience_scope = %s" in query
    assert "COALESCE(o.audience_region_code, o.region_code) = %s" not in query
    assert params == ["party_support", "national", 30]


def test_fetch_trends_query_for_regional_scope_adds_region_filter():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.fetch_trends(metric="party_support", scope="regional", region_code="11-000", days=90)

    query, params = conn._cursor.executed[0]
    assert "COALESCE(o.audience_region_code, o.region_code) = %s" in query
    assert params == ["party_support", "regional", 90, "11-000"]
