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
    assert "WITH official_regions AS" in query
    assert "JOIN official_regions e ON e.region_code = r.region_code" in query
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


def test_region_search_without_query_returns_official_regions():
    conn = _RecordingConn(rows=[{"region_code": "11-000"}])
    repo = PostgresRepository(conn)

    out = repo.search_regions("   ", limit=20)
    assert out == [{"region_code": "11-000"}]
    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "WITH official_regions AS" in query
    assert "WHERE (" not in query
    assert params == (20,)


def test_region_search_has_data_filter_is_optional():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.search_regions("서울", limit=10, has_data=False)

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "COALESCE(o.observation_count, 0)::int > 0 = %s" in query
    assert params[-2:] == (False, 10)


def test_region_search_by_code_uses_exact_match():
    conn = _RecordingConn(rows=[])
    repo = PostgresRepository(conn)

    repo.search_regions_by_code("42-000", limit=10)

    assert len(conn._cursor.executed) == 1
    query, params = conn._cursor.executed[0]
    assert "WITH official_regions AS" in query
    assert "JOIN official_regions e ON e.region_code = r.region_code" in query
    assert "WHERE r.region_code = %s" in query
    assert params == ("42-000", 10)


def test_region_search_by_code_returns_empty_without_region_code():
    conn = _RecordingConn(rows=[{"region_code": "42-000"}])
    repo = PostgresRepository(conn)

    out = repo.search_regions_by_code("   ", limit=20)
    assert out == []
    assert conn._cursor.executed == []
