from datetime import date

import app.services.repository as repository_module
from app.services.repository import PostgresRepository, clear_api_read_cache


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):  # noqa: ARG002
        self._query = query
        if "WITH ranked_latest AS" in query:
            self.conn.summary_query_count += 1
        if "INSERT INTO review_queue" in query:
            self.conn.review_insert_count += 1

    def fetchall(self):
        if "WITH ranked_latest AS" in self._query:
            return [
                {
                    "option_type": "party_support",
                    "option_name": "더불어민주당",
                    "value_mid": 40.0,
                    "pollster": "테스트",
                    "survey_end_date": date(2026, 2, 27),
                    "source_grade": "A",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-27T00:00:00+00:00",
                    "official_release_at": None,
                    "article_published_at": "2026-02-27T00:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                }
            ]
        return []


class _FakeConn:
    def __init__(self):
        self.summary_query_count = 0
        self.review_insert_count = 0
        self.commit_count = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        return None


def test_dashboard_summary_uses_ttl_cache(monkeypatch):
    clear_api_read_cache()
    monkeypatch.setattr(repository_module, "_api_read_cache_ttl_sec", lambda: 30.0)

    conn = _FakeConn()
    repo = PostgresRepository(conn)

    first = repo.fetch_dashboard_summary(as_of=None)
    second = repo.fetch_dashboard_summary(as_of=None)

    assert conn.summary_query_count == 1
    assert first == second


def test_dashboard_summary_cache_disabled_when_ttl_zero(monkeypatch):
    clear_api_read_cache()
    monkeypatch.setattr(repository_module, "_api_read_cache_ttl_sec", lambda: 0.0)

    conn = _FakeConn()
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=None)
    repo.fetch_dashboard_summary(as_of=None)

    assert conn.summary_query_count == 2


def test_write_path_invalidates_dashboard_summary_cache(monkeypatch):
    clear_api_read_cache()
    monkeypatch.setattr(repository_module, "_api_read_cache_ttl_sec", lambda: 30.0)

    conn = _FakeConn()
    repo = PostgresRepository(conn)

    repo.fetch_dashboard_summary(as_of=None)
    repo.fetch_dashboard_summary(as_of=None)
    assert conn.summary_query_count == 1

    repo.insert_review_queue(
        entity_type="ingest_record",
        entity_id="obs-1",
        issue_type="mapping_error",
        review_note="need check",
    )

    repo.fetch_dashboard_summary(as_of=None)

    assert conn.review_insert_count == 1
    assert conn.summary_query_count == 2
