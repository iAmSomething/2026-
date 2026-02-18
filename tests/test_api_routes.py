from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository
from app.main import app


class FakeApiRepo:
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


def override_repo():
    yield FakeApiRepo()


def test_api_contract_fields():
    app.dependency_overrides[get_repository] = override_repo
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
