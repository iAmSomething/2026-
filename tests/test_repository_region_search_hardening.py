from app.services.repository import PostgresRepository


class _RecordingCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple[str, tuple | None]] = []

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


def test_region_search_query_uses_compact_matching_for_space_variants():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.search_regions("서울 특별시", limit=30)

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "REPLACE((sido_name || sigungu_name), ' ', '') ILIKE %s" in query
    assert params == (
        "%서울 특별시%",
        "%서울 특별시%",
        "%서울 특별시%",
        "%서울특별시%",
        "%서울특별시%",
        "%서울특별시%",
        30,
    )


def test_region_search_returns_empty_without_query_text():
    conn = _RecordingConn(rows=[{"region_code": "11-000"}])
    repo = PostgresRepository(conn)

    out = repo.search_regions("   ", limit=20)
    assert out == []
    assert conn._cursor.executed == []
