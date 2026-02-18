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

    candidate = client.get("/api/v1/candidates/cand-jwo")
    assert candidate.status_code == 200
    assert candidate.json()["candidate_id"] == "cand-jwo"

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
