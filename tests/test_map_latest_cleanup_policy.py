from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository
from app.api.routes import _map_latest_exclusion_reason
from app.main import app


def _base_row() -> dict:
    return {
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "title": "서울시장 가상대결",
        "value_mid": 44.0,
        "survey_end_date": date(2026, 2, 26),
        "option_name": "정원오",
        "audience_scope": "regional",
        "audience_region_code": "11-000",
        "observation_updated_at": "2026-02-26T03:00:00+00:00",
        "article_published_at": "2026-02-26T01:00:00+00:00",
        "source_channel": "nesdc",
        "source_channels": ["nesdc"],
    }


def test_map_latest_exclusion_reason_classifies_noise_and_legacy() -> None:
    row = _base_row()
    assert _map_latest_exclusion_reason(row) is None

    noisy = dict(row)
    noisy["option_name"] = "양자대결"
    assert _map_latest_exclusion_reason(noisy) == "invalid_candidate_option_name"

    mixed_token = dict(row)
    mixed_token["option_name"] = "김A"
    assert _map_latest_exclusion_reason(mixed_token) == "invalid_candidate_option_name"

    legacy = dict(row)
    legacy["title"] = "[2022 지방선거] 서울시장 가상대결"
    assert _map_latest_exclusion_reason(legacy) == "legacy_matchup_title"

    old_survey = dict(row)
    old_survey["survey_end_date"] = date(2025, 11, 30)
    assert _map_latest_exclusion_reason(old_survey) == "survey_end_date_before_cutoff"


class _MapLatestPolicyRepo:
    def fetch_dashboard_map_latest(self, as_of, limit=100):  # noqa: ARG002
        valid = _base_row()
        noisy = dict(valid)
        noisy["region_code"] = "26-000"
        noisy["option_name"] = "양자대결"
        legacy = dict(valid)
        legacy["region_code"] = "27-000"
        legacy["title"] = "[2022 지방선거] 대구시장"
        old = dict(valid)
        old["region_code"] = "28-000"
        old["survey_end_date"] = date(2025, 11, 30)
        return [valid, noisy, legacy, old]


def _override_repo():
    yield _MapLatestPolicyRepo()


def test_dashboard_map_latest_filters_invalid_rows_with_cleanup_policy() -> None:
    app.dependency_overrides[get_repository] = _override_repo
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/map-latest", params={"limit": 30})
    app.dependency_overrides.pop(get_repository, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["region_code"] == "11-000"
    assert item["option_name"] == "정원오"
    assert body["scope_breakdown"] == {"national": 0, "regional": 1, "local": 0, "unknown": 0}
