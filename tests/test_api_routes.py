from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_candidate_data_go_service, get_repository
from app.config import get_settings
from app.main import app


class FakeApiRepo:
    def __init__(self):
        self._run_id = 0

    def fetch_dashboard_summary(self, as_of):
        return [
            {
                "option_type": "party_support",
                "option_name": "더불어민주당",
                "value_mid": 42.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "verified": True,
            },
            {
                "option_type": "presidential_approval",
                "option_name": "국정안정론",
                "value_mid": 54.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "verified": True,
            },
        ]

    def search_regions(self, query, limit=20):
        return [
            {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        ]

    def fetch_dashboard_map_latest(self, as_of, limit=100):
        return [
            {
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "value_mid": 44.0,
                "survey_end_date": date(2026, 2, 18),
                "option_name": "정원오",
            }
        ]

    def fetch_dashboard_big_matches(self, as_of, limit=3):
        return [
            {
                "matchup_id": "20260603|광역자치단체장|11-000",
                "title": "서울시장 가상대결",
                "survey_end_date": date(2026, 2, 18),
                "value_mid": 44.0,
                "spread": 2.0,
            }
        ]

    def fetch_region_elections(self, region_code):
        return [
            {
                "matchup_id": "20260603|광역자치단체장|11-000",
                "region_code": region_code,
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "is_active": True,
            }
        ]

    def get_matchup(self, matchup_id):
        if matchup_id == "missing":
            return None
        return {
            "matchup_id": matchup_id,
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "title": "서울시장 가상대결",
            "pollster": "KBS",
            "survey_end_date": date(2026, 2, 18),
            "margin_of_error": 3.1,
            "source_grade": "B",
            "audience_scope": "regional",
            "audience_region_code": "11-000",
            "sampling_population_text": "서울시 거주 만 18세 이상",
            "legal_completeness_score": 0.86,
            "legal_filled_count": 6,
            "legal_required_count": 7,
            "date_resolution": "exact",
            "poll_fingerprint": "f" * 64,
            "source_channel": "article",
            "verified": True,
            "options": [
                {"option_name": "정원오", "value_mid": 44.0, "value_raw": "44%"},
                {"option_name": "오세훈", "value_mid": 42.0, "value_raw": "42%"},
            ],
        }

    def get_candidate(self, candidate_id):
        if candidate_id == "missing":
            return None
        return {
            "candidate_id": candidate_id,
            "name_ko": "정원오",
            "party_name": "더불어민주당",
            "gender": "M",
            "birth_date": date(1968, 8, 12),
            "job": "구청장",
            "career_summary": "성동구청장",
            "election_history": "지방선거 출마",
        }

    def fetch_ops_ingestion_metrics(self, window_hours=24):  # noqa: ARG002
        return {
            "total_runs": 12,
            "success_runs": 10,
            "partial_success_runs": 1,
            "failed_runs": 1,
            "total_processed_count": 500,
            "total_error_count": 30,
            "fetch_fail_rate": 0.0566,
        }

    def fetch_ops_review_metrics(self, window_hours=24):  # noqa: ARG002
        return {
            "pending_count": 4,
            "in_progress_count": 2,
            "resolved_count": 11,
            "pending_over_24h_count": 1,
            "mapping_error_24h_count": 2,
        }

    def fetch_ops_failure_distribution(self, window_hours=24):  # noqa: ARG002
        return [
            {"issue_type": "mapping_error", "count": 2, "ratio": 0.5},
            {"issue_type": "value_conflict", "count": 2, "ratio": 0.5},
        ]

    def fetch_ops_coverage_summary(self):
        return {
            "state": "ready",
            "warning_message": None,
            "regions_total": 11,
            "regions_covered": 11,
            "sido_covered": 6,
            "observations_total": 100,
            "latest_survey_end_date": date(2026, 2, 19),
        }

    def fetch_review_queue_items(  # noqa: ARG002
        self,
        *,
        status=None,
        issue_type=None,
        assigned_to=None,
        limit=50,
        offset=0,
    ):
        rows = [
            {
                "id": 101,
                "entity_type": "ingest_record",
                "entity_id": "obs-1",
                "issue_type": "ingestion_error",
                "status": "pending",
                "assigned_to": "qa.user",
                "review_note": "invalid region code",
                "created_at": "2026-02-18T14:00:00+00:00",
                "updated_at": "2026-02-18T14:10:00+00:00",
            },
            {
                "id": 100,
                "entity_type": "ingest_record",
                "entity_id": "obs-0",
                "issue_type": "mapping_error:region_not_found",
                "status": "in_progress",
                "assigned_to": None,
                "review_note": "manual check required",
                "created_at": "2026-02-18T13:00:00+00:00",
                "updated_at": "2026-02-18T13:05:00+00:00",
            },
        ]
        if status:
            rows = [r for r in rows if r["status"] == status]
        if issue_type:
            rows = [r for r in rows if r["issue_type"] == issue_type]
        if assigned_to:
            rows = [r for r in rows if r["assigned_to"] == assigned_to]
        return rows[offset : offset + limit]

    def fetch_review_queue_stats(self, *, window_hours=24):  # noqa: ARG002
        return {
            "total_count": 7,
            "pending_count": 3,
            "in_progress_count": 2,
            "resolved_count": 2,
            "issue_type_counts": [
                {"issue_type": "ingestion_error", "count": 3},
                {"issue_type": "mapping_error:region_not_found", "count": 2},
            ],
            "error_code_counts": [
                {"error_code": "region_not_found", "count": 2},
                {"error_code": "unknown", "count": 5},
            ],
        }

    def fetch_review_queue_trends(  # noqa: ARG002
        self,
        *,
        window_hours=24,
        bucket_hours=6,
        issue_type=None,
        error_code=None,
    ):
        rows = [
            {
                "bucket_start": "2026-02-18T12:00:00+00:00",
                "issue_type": "ingestion_error",
                "error_code": "unknown",
                "count": 2,
            },
            {
                "bucket_start": "2026-02-18T12:00:00+00:00",
                "issue_type": "mapping_error",
                "error_code": "region_not_found",
                "count": 1,
            },
        ]
        if issue_type:
            rows = [r for r in rows if r["issue_type"] == issue_type]
        if error_code:
            rows = [r for r in rows if r["error_code"] == error_code]
        return rows

    def create_ingestion_run(self, run_type, extractor_version, llm_model):
        self._run_id += 1
        return self._run_id

    def finish_ingestion_run(self, run_id, status, processed_count, error_count):
        return None

    def upsert_region(self, region):
        return None

    def upsert_matchup(self, matchup):
        return None

    def upsert_candidate(self, candidate):
        return None

    def upsert_article(self, article):
        return 1

    def upsert_poll_observation(self, observation, article_id, ingestion_run_id):
        return 1

    def upsert_poll_option(self, observation_id, option):
        return None

    def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
        return None


def override_repo():
    yield FakeApiRepo()


class FakeCandidateDataGoService:
    def __init__(self, merged_fields: dict | None = None):
        self.merged_fields = merged_fields or {}

    def enrich_candidate(self, candidate: dict):
        out = dict(candidate)
        out.update(self.merged_fields)
        return out


def override_candidate_data_go_service():
    return FakeCandidateDataGoService()


def test_api_contract_fields():
    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    summary = client.get("/api/v1/dashboard/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert "party_support" in body
    assert "presidential_approval" in body
    assert "option_name" in body["party_support"][0]
    assert "value_mid" in body["party_support"][0]

    regions = client.get("/api/v1/regions/search", params={"q": "서울"})
    assert regions.status_code == 200
    assert regions.json()[0]["region_code"] == "11-000"

    map_latest = client.get("/api/v1/dashboard/map-latest")
    assert map_latest.status_code == 200
    assert map_latest.json()["items"][0]["region_code"] == "11-000"

    big_matches = client.get("/api/v1/dashboard/big-matches")
    assert big_matches.status_code == 200
    assert big_matches.json()["items"][0]["matchup_id"] == "20260603|광역자치단체장|11-000"

    region_elections = client.get("/api/v1/regions/11-000/elections")
    assert region_elections.status_code == 200
    assert region_elections.json()[0]["is_active"] is True

    matchup = client.get("/api/v1/matchups/20260603|광역자치단체장|11-000")
    assert matchup.status_code == 200
    assert matchup.json()["options"][0]["option_name"] == "정원오"
    assert matchup.json()["audience_scope"] == "regional"
    assert matchup.json()["legal_required_count"] == 7
    assert matchup.json()["source_channel"] == "article"

    candidate = client.get("/api/v1/candidates/cand-jwo")
    assert candidate.status_code == 200
    assert candidate.json()["candidate_id"] == "cand-jwo"

    ops = client.get("/api/v1/ops/metrics/summary")
    assert ops.status_code == 200
    ops_body = ops.json()
    assert ops_body["window_hours"] == 24
    assert "ingestion" in ops_body
    assert "review_queue" in ops_body
    assert isinstance(ops_body["warnings"], list)
    assert len(ops_body["warnings"]) >= 2

    coverage = client.get("/api/v1/ops/coverage/summary")
    assert coverage.status_code == 200
    coverage_body = coverage.json()
    assert coverage_body["state"] == "ready"
    assert coverage_body["warning_message"] is None
    assert coverage_body["regions_total"] == 11
    assert coverage_body["regions_covered"] == 11
    assert coverage_body["sido_covered"] == 6
    assert coverage_body["observations_total"] == 100
    assert coverage_body["latest_survey_end_date"] == "2026-02-19"

    review_items = client.get(
        "/api/v1/review-queue/items",
        params={"status": "pending", "limit": 10, "offset": 0},
    )
    assert review_items.status_code == 200
    items_body = review_items.json()
    assert len(items_body) == 1
    assert items_body[0]["issue_type"] == "ingestion_error"

    review_stats = client.get("/api/v1/review-queue/stats", params={"window_hours": 48})
    assert review_stats.status_code == 200
    stats_body = review_stats.json()
    assert stats_body["window_hours"] == 48
    assert stats_body["total_count"] == 7
    assert stats_body["issue_type_counts"][0]["issue_type"] == "ingestion_error"
    assert stats_body["error_code_counts"][0]["error_code"] == "region_not_found"

    review_trends = client.get(
        "/api/v1/review-queue/trends",
        params={"window_hours": 24, "bucket_hours": 6, "error_code": "region_not_found"},
    )
    assert review_trends.status_code == 200
    trends_body = review_trends.json()
    assert trends_body["bucket_hours"] == 6
    assert len(trends_body["points"]) == 1
    assert trends_body["points"][0]["error_code"] == "region_not_found"

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("summary", "expected_state", "expected_warning"),
    [
        (
            {
                "state": "ready",
                "warning_message": None,
                "regions_total": 11,
                "regions_covered": 11,
                "sido_covered": 6,
                "observations_total": 100,
                "latest_survey_end_date": date(2026, 2, 19),
            },
            "ready",
            None,
        ),
        (
            {
                "state": "partial",
                "warning_message": "Coverage partial: 6/11 regions covered.",
                "regions_total": 11,
                "regions_covered": 6,
                "sido_covered": 6,
                "observations_total": 40,
                "latest_survey_end_date": date(2026, 2, 18),
            },
            "partial",
            "Coverage partial: 6/11 regions covered.",
        ),
        (
            {
                "state": "empty",
                "warning_message": "No observations ingested yet.",
                "regions_total": 11,
                "regions_covered": 0,
                "sido_covered": 0,
                "observations_total": 0,
                "latest_survey_end_date": None,
            },
            "empty",
            "No observations ingested yet.",
        ),
    ],
)
def test_ops_coverage_summary_state_contract(summary, expected_state, expected_warning):
    class CoverageRepo(FakeApiRepo):
        def fetch_ops_coverage_summary(self):
            return summary

    def override_coverage_repo():
        yield CoverageRepo()

    app.dependency_overrides[get_repository] = override_coverage_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/ops/coverage/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == expected_state
    assert body["warning_message"] == expected_warning
    assert "regions_total" in body
    assert "regions_covered" in body
    assert "sido_covered" in body
    assert "observations_total" in body
    assert "latest_survey_end_date" in body

    app.dependency_overrides.clear()


def test_run_ingest_requires_bearer_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.setenv("DATA_GO_KR_KEY", "test-data-go-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "dev-internal-token")
    get_settings.cache_clear()

    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    payload = {
        "run_type": "manual",
        "extractor_version": "manual-v1",
        "records": [
            {
                "article": {"url": "https://example.com/1", "title": "sample", "publisher": "pub"},
                "region": {
                    "region_code": "11-000",
                    "sido_name": "서울특별시",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                },
                "observation": {
                    "observation_key": "obs-1",
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "20260603|광역자치단체장|11-000",
                },
                "options": [
                    {"option_type": "presidential_approval", "option_name": "국정안정론", "value_raw": "53~55%"}
                ],
            }
        ],
    }

    missing = client.post("/api/v1/jobs/run-ingest", json=payload)
    assert missing.status_code == 401

    invalid = client.post(
        "/api/v1/jobs/run-ingest",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert invalid.status_code == 403

    ok = client.post(
        "/api/v1/jobs/run-ingest",
        json=payload,
        headers={"Authorization": "Bearer dev-internal-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "success"

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_candidate_endpoint_merges_data_go_fields():
    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_candidate_data_go_service] = lambda: FakeCandidateDataGoService(
        {
            "party_name": "공공데이터정당",
            "job": "공공데이터직업",
        }
    )
    client = TestClient(app)

    res = client.get("/api/v1/candidates/cand-jwo")
    assert res.status_code == 200
    body = res.json()
    assert body["candidate_id"] == "cand-jwo"
    assert body["party_name"] == "공공데이터정당"
    assert body["job"] == "공공데이터직업"

    app.dependency_overrides.clear()
