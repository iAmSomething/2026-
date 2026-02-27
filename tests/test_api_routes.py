from datetime import date
import unicodedata

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_candidate_data_go_service, get_repository
from app.config import get_settings
from app.main import app


class FakeApiRepo:
    def __init__(self):
        self._run_id = 0
        self._review_items = [
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

    def fetch_dashboard_summary(self, as_of):
        return [
            {
                "option_type": "party_support",
                "option_name": "더불어민주당",
                "value_mid": 42.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "audience_scope": "national",
                "audience_region_code": None,
                "observation_updated_at": "2026-02-18T03:00:00+00:00",
                "article_published_at": "2026-02-18T01:00:00+00:00",
                "source_channel": "nesdc",
                "source_channels": ["article", "nesdc"],
                "verified": True,
            },
            {
                "option_type": "party_support",
                "option_name": "지역정당A",
                "value_mid": 22.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "audience_scope": "regional",
                "audience_region_code": "11-000",
                "observation_updated_at": "2026-02-18T02:00:00+00:00",
                "article_published_at": "2026-02-18T01:30:00+00:00",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
            },
            {
                "option_type": "president_job_approval",
                "option_name": "대통령 직무 긍정평가",
                "value_mid": 51.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "audience_scope": "national",
                "audience_region_code": None,
                "observation_updated_at": "2026-02-18T03:20:00+00:00",
                "article_published_at": "2026-02-18T02:50:00+00:00",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
            },
            {
                "option_type": "election_frame",
                "option_name": "국정안정론",
                "value_mid": 54.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "audience_scope": "national",
                "audience_region_code": None,
                "observation_updated_at": "2026-02-18T03:30:00+00:00",
                "article_published_at": "2026-02-18T03:00:00+00:00",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
            },
            {
                "option_type": "presidential_approval",
                "option_name": "지역이슈안정론",
                "value_mid": 33.0,
                "pollster": "KBS",
                "survey_end_date": date(2026, 2, 18),
                "audience_scope": "local",
                "audience_region_code": "11-110",
                "observation_updated_at": "2026-02-18T04:00:00+00:00",
                "article_published_at": "2026-02-18T03:30:00+00:00",
                "source_channel": "article",
                "source_channels": ["article"],
                "verified": True,
            },
        ]

    def search_regions(self, query, limit=20, has_data=None):
        rows = [
            {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
                "has_data": True,
                "matchup_count": 1,
            }
        ]
        if has_data is None:
            return rows
        return [row for row in rows if row["has_data"] is has_data][:limit]

    def search_regions_by_code(self, region_code, limit=20, has_data=None):  # noqa: ARG002
        if region_code == "42-000":
            rows = [
                {
                    "region_code": "42-000",
                    "sido_name": "강원특별자치도",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                    "has_data": True,
                    "matchup_count": 1,
                }
            ]
            if has_data is None:
                return rows
            return [row for row in rows if row["has_data"] is has_data][:limit]
        return self.search_regions(query=region_code, limit=limit, has_data=has_data)

    def fetch_dashboard_map_latest(self, as_of, limit=100):
        return [
            {
                "region_code": "11-000",
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "value_mid": 44.0,
                "survey_end_date": date(2026, 2, 18),
                "option_name": "정원오",
                "audience_scope": "regional",
                "audience_region_code": "11-000",
                "observation_updated_at": "2026-02-18T03:00:00+00:00",
                "article_published_at": "2026-02-18T01:00:00+00:00",
                "source_channel": "nesdc",
                "source_channels": ["article", "nesdc"],
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
                "audience_scope": "regional",
                "audience_region_code": "11-000",
                "observation_updated_at": "2026-02-18T03:00:00+00:00",
                "article_published_at": "2026-02-18T01:00:00+00:00",
                "source_channel": "nesdc",
                "source_channels": ["article", "nesdc"],
            }
        ]

    def fetch_region_elections(self, region_code, topology="official", version_id=None):  # noqa: ARG002
        return [
            {
                "matchup_id": "20260603|광역자치단체장|11-000",
                "region_code": region_code,
                "office_type": "광역자치단체장",
                "title": "서울시장 가상대결",
                "is_active": True,
                "topology": topology,
                "topology_version_id": version_id,
                "is_placeholder": False,
                "is_fallback": False,
                "source": "master",
                "has_poll_data": True,
                "has_candidate_data": True,
                "latest_survey_end_date": date(2026, 2, 18),
                "latest_matchup_id": "20260603|광역자치단체장|11-000",
                "status": "데이터 준비 완료",
            }
        ]

    def get_matchup(self, matchup_id):
        if matchup_id == "missing":
            return None
        if matchup_id == "2026_local|기초자치단체장|26-710":
            return {
                "matchup_id": "20260603|기초자치단체장|26-710",
                "region_code": "26-710",
                "office_type": "기초자치단체장",
                "title": "부산 중구청장 가상대결",
                "has_data": False,
                "pollster": None,
                "survey_start_date": None,
                "survey_end_date": None,
                "confidence_level": None,
                "sample_size": None,
                "response_rate": None,
                "margin_of_error": None,
                "source_grade": None,
                "audience_scope": None,
                "audience_region_code": None,
                "sampling_population_text": None,
                "legal_completeness_score": None,
                "legal_filled_count": None,
                "legal_required_count": None,
                "date_resolution": None,
                "date_inference_mode": None,
                "date_inference_confidence": None,
                "observation_updated_at": None,
                "article_published_at": None,
                "official_release_at": None,
                "nesdc_enriched": False,
                "needs_manual_review": False,
                "poll_fingerprint": None,
                "source_channel": None,
                "source_channels": [],
                "verified": False,
                "scenarios": [],
                "options": [],
            }
        return {
            "matchup_id": matchup_id,
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "title": "서울시장 가상대결",
            "has_data": True,
            "pollster": "KBS",
            "survey_start_date": date(2026, 2, 15),
            "survey_end_date": date(2026, 2, 18),
            "confidence_level": 95.0,
            "sample_size": 1000,
            "response_rate": 12.3,
            "margin_of_error": 3.1,
            "source_grade": "B",
            "audience_scope": "regional",
            "audience_region_code": "11-000",
            "sampling_population_text": "서울시 거주 만 18세 이상",
            "legal_completeness_score": 0.86,
            "legal_filled_count": 6,
            "legal_required_count": 7,
            "date_resolution": "exact",
            "date_inference_mode": "relative_published_at",
            "date_inference_confidence": 0.92,
            "observation_updated_at": "2026-02-18T03:00:00+00:00",
            "article_published_at": "2026-02-18T01:00:00+00:00",
            "nesdc_enriched": True,
            "needs_manual_review": True,
            "poll_fingerprint": "f" * 64,
            "source_channel": "article",
            "source_channels": ["article", "nesdc"],
            "verified": True,
            "scenarios": [
                {
                    "scenario_key": "h2h-jwo-oh",
                    "scenario_type": "head_to_head",
                    "scenario_title": "정원오 vs 오세훈",
                    "options": [
                        {
                            "option_name": "정원오",
                            "candidate_id": "cand-jwo",
                            "party_name": "더불어민주당",
                            "scenario_key": "h2h-jwo-oh",
                            "scenario_type": "head_to_head",
                            "scenario_title": "정원오 vs 오세훈",
                            "value_mid": 44.0,
                            "value_raw": "44%",
                            "party_inferred": True,
                            "party_inference_source": "name_rule",
                            "party_inference_confidence": 0.86,
                            "needs_manual_review": False,
                        },
                        {
                            "option_name": "오세훈",
                            "candidate_id": "cand-oh",
                            "party_name": "국민의힘",
                            "scenario_key": "h2h-jwo-oh",
                            "scenario_type": "head_to_head",
                            "scenario_title": "정원오 vs 오세훈",
                            "value_mid": 42.0,
                            "value_raw": "42%",
                            "party_inferred": False,
                            "party_inference_source": None,
                            "party_inference_confidence": None,
                            "needs_manual_review": True,
                        },
                    ],
                }
            ],
            "options": [
                {
                    "option_name": "정원오",
                    "candidate_id": "cand-jwo",
                    "party_name": "더불어민주당",
                    "scenario_key": "h2h-jwo-oh",
                    "scenario_type": "head_to_head",
                    "scenario_title": "정원오 vs 오세훈",
                    "value_mid": 44.0,
                    "value_raw": "44%",
                    "party_inferred": True,
                    "party_inference_source": "name_rule",
                    "party_inference_confidence": 0.86,
                    "needs_manual_review": False,
                },
                {
                    "option_name": "오세훈",
                    "candidate_id": "cand-oh",
                    "party_name": "국민의힘",
                    "scenario_key": "h2h-jwo-oh",
                    "scenario_type": "head_to_head",
                    "scenario_title": "정원오 vs 오세훈",
                    "value_mid": 42.0,
                    "value_raw": "42%",
                    "party_inferred": False,
                    "party_inference_source": None,
                    "party_inference_confidence": None,
                    "needs_manual_review": True,
                },
            ],
        }

    def get_candidate(self, candidate_id):
        if candidate_id == "missing":
            return None
        return {
            "candidate_id": candidate_id,
            "name_ko": "정원오",
            "party_name": "더불어민주당",
            "party_inferred": True,
            "party_inference_source": "name_rule",
            "party_inference_confidence": 0.91,
            "needs_manual_review": False,
            "source_channel": "nesdc",
            "source_channels": ["article", "nesdc"],
            "observation_updated_at": "2026-02-18T04:00:00+00:00",
            "article_published_at": "2026-02-18T02:00:00+00:00",
            "official_release_at": None,
            "gender": "M",
            "birth_date": date(1968, 8, 12),
            "job": "구청장",
            "career_summary": "성동구청장",
            "election_history": "지방선거 출마",
            "profile_source_type": "manual",
            "profile_source_url": None,
        }

    def fetch_ops_ingestion_metrics(self, window_hours=24):  # noqa: ARG002
        return {
            "total_runs": 12,
            "success_runs": 10,
            "partial_success_runs": 1,
            "failed_runs": 1,
            "total_processed_count": 500,
            "total_error_count": 30,
            "date_inference_failed_count": 2,
            "date_inference_estimated_count": 5,
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

    def fetch_dashboard_quality(self):
        return {
            "quality_status": "warn",
            "freshness_p50_hours": 18.5,
            "freshness_p90_hours": 42.25,
            "official_confirmed_ratio": 0.6,
            "needs_manual_review_count": 4,
            "source_channel_mix": {"article_ratio": 0.8, "nesdc_ratio": 0.6},
            "freshness": {
                "p50_hours": 18.5,
                "p90_hours": 42.25,
                "over_24h_ratio": 0.25,
                "over_48h_ratio": 0.05,
                "status": "warn",
            },
            "official_confirmation": {
                "confirmed_ratio": 0.6,
                "unconfirmed_count": 4,
                "status": "warn",
            },
            "review_queue": {
                "pending_count": 3,
                "in_progress_count": 1,
                "pending_over_24h_count": 1,
            },
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
        rows = list(self._review_items)
        if status:
            rows = [r for r in rows if r["status"] == status]
        if issue_type:
            rows = [r for r in rows if r["issue_type"] == issue_type]
        if assigned_to:
            rows = [r for r in rows if r["assigned_to"] == assigned_to]
        return rows[offset : offset + limit]

    def update_review_queue_status(self, *, item_id, status, assigned_to=None, review_note=None):  # noqa: ARG002
        for row in self._review_items:
            if row["id"] != item_id:
                continue
            row["status"] = status
            if assigned_to is not None:
                row["assigned_to"] = assigned_to
            if review_note is not None:
                row["review_note"] = review_note
            row["updated_at"] = "2026-02-19T00:00:00+00:00"
            return dict(row)
        return None

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
    assert "president_job_approval" in body
    assert "election_frame" in body
    assert "presidential_approval" in body
    assert body["presidential_approval_deprecated"] is True
    assert body["data_source"] == "mixed"
    assert "option_name" in body["party_support"][0]
    assert "value_mid" in body["party_support"][0]
    assert "source_channels" in body["party_support"][0]
    assert body["party_support"][0]["source_channels"] == ["article", "nesdc"]
    assert body["party_support"][0]["audience_scope"] == "national"
    assert "audience_region_code" in body["party_support"][0]
    assert all(
        x["audience_scope"] == "national"
        for x in body["party_support"] + body["president_job_approval"] + body["election_frame"] + body["presidential_approval"]
    )
    assert [x["option_name"] for x in body["party_support"]] == ["더불어민주당"]
    assert [x["option_name"] for x in body["president_job_approval"]] == ["대통령 직무 긍정평가"]
    assert [x["option_name"] for x in body["election_frame"]] == ["국정안정론"]
    assert [x["option_name"] for x in body["presidential_approval"]] == ["대통령 직무 긍정평가"]
    assert body["scope_breakdown"] == {"national": 3, "regional": 1, "local": 1, "unknown": 0}
    assert body["party_support"][0]["source_priority"] == "mixed"
    assert body["party_support"][0]["is_official_confirmed"] is True
    assert isinstance(body["party_support"][0]["freshness_hours"], float)
    assert body["party_support"][0]["article_published_at"] is not None
    assert body["party_support"][0]["official_release_at"] is not None

    regions = client.get("/api/v1/regions/search", params={"q": "서울"})
    assert regions.status_code == 200
    assert regions.json()[0]["region_code"] == "11-000"
    assert regions.json()[0]["has_data"] is True
    assert regions.json()[0]["matchup_count"] == 1
    regions_query_alias = client.get("/api/v1/regions/search", params={"query": "서울"})
    assert regions_query_alias.status_code == 200
    assert regions_query_alias.json()[0]["region_code"] == "11-000"
    regions_missing = client.get("/api/v1/regions/search")
    assert regions_missing.status_code == 200
    assert regions_missing.json()[0]["region_code"] == "11-000"

    map_latest = client.get("/api/v1/dashboard/map-latest")
    assert map_latest.status_code == 200
    assert map_latest.json()["items"][0]["region_code"] == "11-000"
    assert map_latest.json()["items"][0]["source_channels"] == ["article", "nesdc"]
    assert map_latest.json()["items"][0]["audience_scope"] == "regional"
    assert map_latest.json()["items"][0]["audience_region_code"] == "11-000"
    assert map_latest.json()["scope_breakdown"] == {"national": 0, "regional": 1, "local": 0, "unknown": 0}
    assert map_latest.json()["items"][0]["source_priority"] == "mixed"
    assert map_latest.json()["items"][0]["is_official_confirmed"] is True
    assert isinstance(map_latest.json()["items"][0]["freshness_hours"], float)
    assert map_latest.json()["filter_stats"]["total_count"] == 1
    assert map_latest.json()["filter_stats"]["kept_count"] == 1
    assert map_latest.json()["filter_stats"]["excluded_count"] == 0
    assert map_latest.json()["filter_stats"]["reason_counts"] == {}

    big_matches = client.get("/api/v1/dashboard/big-matches")
    assert big_matches.status_code == 200
    assert big_matches.json()["items"][0]["matchup_id"] == "20260603|광역자치단체장|11-000"
    assert big_matches.json()["items"][0]["source_channels"] == ["article", "nesdc"]
    assert big_matches.json()["items"][0]["audience_scope"] == "regional"
    assert big_matches.json()["items"][0]["audience_region_code"] == "11-000"
    assert big_matches.json()["items"][0]["source_priority"] == "mixed"
    assert big_matches.json()["items"][0]["is_official_confirmed"] is True
    assert isinstance(big_matches.json()["items"][0]["freshness_hours"], float)
    assert big_matches.json()["items"][0]["article_published_at"] is not None
    assert big_matches.json()["items"][0]["official_release_at"] is not None
    assert big_matches.json()["scope_breakdown"] == {"national": 0, "regional": 1, "local": 0, "unknown": 0}

    quality = client.get("/api/v1/dashboard/quality")
    assert quality.status_code == 200
    quality_body = quality.json()
    assert "generated_at" in quality_body
    assert quality_body["freshness_p50_hours"] == 18.5
    assert quality_body["freshness_p90_hours"] == 42.25
    assert quality_body["official_confirmed_ratio"] == 0.6
    assert quality_body["needs_manual_review_count"] == 4
    assert quality_body["source_channel_mix"]["article_ratio"] == 0.8
    assert quality_body["source_channel_mix"]["nesdc_ratio"] == 0.6
    assert quality_body["quality_status"] == "warn"
    assert quality_body["freshness"]["status"] == "warn"
    assert quality_body["freshness"]["over_24h_ratio"] == 0.25
    assert quality_body["official_confirmation"]["confirmed_ratio"] == 0.6
    assert quality_body["official_confirmation"]["unconfirmed_count"] == 4
    assert quality_body["review_queue"]["pending_count"] == 3
    assert quality_body["review_queue"]["in_progress_count"] == 1
    assert quality_body["review_queue"]["pending_over_24h_count"] == 1

    region_elections = client.get("/api/v1/regions/11-000/elections")
    assert region_elections.status_code == 200
    region_election_row = region_elections.json()[0]
    assert region_election_row["is_active"] is True
    assert region_election_row["topology"] == "official"
    assert "has_poll_data" in region_election_row
    assert "is_fallback" in region_election_row
    assert "source" in region_election_row
    assert "latest_survey_end_date" in region_election_row
    assert "latest_matchup_id" in region_election_row
    assert "status" in region_election_row

    matchup = client.get("/api/v1/matchups/20260603|광역자치단체장|11-000")
    assert matchup.status_code == 200
    assert matchup.json()["has_data"] is True
    assert "canonical_title" in matchup.json()
    assert "article_title" in matchup.json()
    assert matchup.json()["options"][0]["option_name"] == "정원오"
    assert matchup.json()["survey_start_date"] == "2026-02-15"
    assert matchup.json()["audience_scope"] == "regional"
    assert matchup.json()["confidence_level"] == 95.0
    assert matchup.json()["sample_size"] == 1000
    assert matchup.json()["response_rate"] == 12.3
    assert matchup.json()["legal_required_count"] == 7
    assert matchup.json()["date_inference_mode"] == "relative_published_at"
    assert matchup.json()["date_inference_confidence"] == 0.92
    assert matchup.json()["nesdc_enriched"] is True
    assert matchup.json()["needs_manual_review"] is True
    assert matchup.json()["source_priority"] == "mixed"
    assert matchup.json()["is_official_confirmed"] is True
    assert isinstance(matchup.json()["freshness_hours"], float)
    assert matchup.json()["article_published_at"] is not None
    assert matchup.json()["official_release_at"] is not None
    assert matchup.json()["source_channel"] == "article"
    assert matchup.json()["source_channels"] == ["article", "nesdc"]
    assert matchup.json()["scenarios"][0]["scenario_type"] == "head_to_head"
    assert matchup.json()["scenarios"][0]["scenario_title"] == "정원오 vs 오세훈"
    assert matchup.json()["options"][0]["party_inferred"] is True
    assert matchup.json()["options"][0]["party_inference_source"] == "name_rule"
    assert matchup.json()["options"][0]["party_inference_confidence"] == 0.86
    assert matchup.json()["options"][0]["candidate_id"] == "cand-jwo"
    assert matchup.json()["options"][0]["party_name"] == "더불어민주당"
    assert matchup.json()["options"][0]["needs_manual_review"] is False
    assert matchup.json()["options"][1]["needs_manual_review"] is True
    assert matchup.json()["options"][1]["candidate_id"] == "cand-oh"
    matchup_alias = client.get("/api/v1/matchups/m_2026_seoul_mayor")
    assert matchup_alias.status_code == 200
    assert matchup_alias.json()["matchup_id"] == "20260603|광역자치단체장|11-000"
    matchup_meta_only = client.get("/api/v1/matchups/2026_local|기초자치단체장|26-710")
    assert matchup_meta_only.status_code == 200
    assert matchup_meta_only.json()["matchup_id"] == "20260603|기초자치단체장|26-710"
    assert matchup_meta_only.json()["has_data"] is False
    assert matchup_meta_only.json()["scenarios"] == []
    assert matchup_meta_only.json()["options"] == []

    candidate = client.get("/api/v1/candidates/cand-jwo")
    assert candidate.status_code == 200
    assert candidate.json()["candidate_id"] == "cand-jwo"
    assert candidate.json()["party_inferred"] is True
    assert candidate.json()["party_inference_source"] == "name_rule"
    assert candidate.json()["party_inference_confidence"] == 0.91
    assert candidate.json()["needs_manual_review"] is False
    assert isinstance(candidate.json()["party_inferred"], bool)
    assert isinstance(candidate.json()["needs_manual_review"], bool)
    assert candidate.json()["source_priority"] == "mixed"
    assert candidate.json()["is_official_confirmed"] is True
    assert isinstance(candidate.json()["freshness_hours"], float)
    assert candidate.json()["source_channel"] == "nesdc"
    assert candidate.json()["source_channels"] == ["article", "nesdc"]
    assert candidate.json()["article_published_at"] is not None
    assert candidate.json()["official_release_at"] is not None
    assert candidate.json()["profile_source"] == "ingest"
    assert candidate.json()["profile_completeness"] == "complete"
    assert candidate.json()["placeholder_name_applied"] is False
    assert candidate.json()["profile_source_type"] == "manual"
    assert candidate.json()["profile_provenance"]["career_summary"] == "ingest"
    assert candidate.json()["profile_provenance"]["election_history"] == "ingest"

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


def test_map_latest_sanity_filter_drops_invalid_candidate_and_legacy_title_rows():
    class MapSanityRepo(FakeApiRepo):
        def fetch_dashboard_map_latest(self, as_of, limit=100):  # noqa: ARG002
            return [
                {
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "title": "서울시장 가상대결",
                    "value_mid": 44.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "오세훈",
                    "audience_scope": "regional",
                    "audience_region_code": "11-000",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "nesdc",
                    "source_channels": ["article", "nesdc"],
                },
                {
                    "region_code": "11-010",
                    "office_type": "기초자치단체장",
                    "title": "종로구청장 가상대결",
                    "value_mid": 40.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "김A",
                    "audience_scope": "local",
                    "audience_region_code": "11-010",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-020",
                    "office_type": "기초자치단체장",
                    "title": "중구청장 가상대결",
                    "value_mid": 39.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "양자대결",
                    "audience_scope": "local",
                    "audience_region_code": "11-020",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-030",
                    "office_type": "기초자치단체장",
                    "title": "2022 서울시장 선거 가상대결",
                    "value_mid": 38.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "박형준",
                    "audience_scope": "local",
                    "audience_region_code": "11-030",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-040",
                    "office_type": "기초자치단체장",
                    "title": "부천시 여론조사 요약",
                    "value_mid": 24.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "재정자립도",
                    "audience_scope": "local",
                    "audience_region_code": "11-040",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-050",
                    "office_type": "기초자치단체장",
                    "title": "지방선거 여론조사",
                    "value_mid": 58.5,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "지지",
                    "audience_scope": "local",
                    "audience_region_code": "11-050",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
            ][:limit]

    def override_sanity_repo():
        yield MapSanityRepo()

    app.dependency_overrides[get_repository] = override_sanity_repo
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/map-latest")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["option_name"] == "오세훈"
    assert body["filter_stats"]["total_count"] == 6
    assert body["filter_stats"]["kept_count"] == 1
    assert body["filter_stats"]["excluded_count"] == 5
    assert body["filter_stats"]["reason_counts"]["invalid_candidate_name"] == 1
    assert body["filter_stats"]["reason_counts"]["generic_option_token"] == 3
    assert body["filter_stats"]["reason_counts"]["legacy_title"] == 1
    assert body["scope_breakdown"] == {"national": 0, "regional": 1, "local": 0, "unknown": 0}

    app.dependency_overrides.clear()


def test_dashboard_summary_selects_single_representative_by_source_priority():
    class SummaryRepresentativeRepo(FakeApiRepo):
        def fetch_dashboard_summary(self, as_of):  # noqa: ARG002
            return [
                {
                    "option_type": "party_support",
                    "option_name": "더불어민주당",
                    "value_mid": 35.0,
                    "pollster": "기사집계센터",
                    "survey_end_date": date(2026, 2, 20),
                    "source_grade": "A",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-20T03:00:00+00:00",
                    "article_published_at": "2026-02-20T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "party_support",
                    "option_name": "더불어민주당",
                    "value_mid": 34.0,
                    "pollster": "NBS",
                    "survey_end_date": date(2026, 2, 18),
                    "source_grade": "B",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "official_release_at": "2026-02-18T01:00:00+00:00",
                    "article_published_at": None,
                    "source_channel": "nesdc",
                    "source_channels": ["nesdc"],
                    "verified": True,
                },
                {
                    "option_type": "party_support",
                    "option_name": "국민의힘",
                    "value_mid": 39.0,
                    "pollster": "기사집계센터",
                    "survey_end_date": date(2026, 2, 18),
                    "source_grade": "B",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-02-18T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "party_support",
                    "option_name": "국민의힘",
                    "value_mid": 40.0,
                    "pollster": "일반기사",
                    "survey_end_date": date(2026, 2, 20),
                    "source_grade": "A",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-20T03:00:00+00:00",
                    "article_published_at": "2026-02-20T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "president_job_approval",
                    "option_name": "대통령 직무 긍정평가",
                    "value_mid": 47.0,
                    "pollster": "일반기사",
                    "survey_end_date": date(2026, 2, 20),
                    "source_grade": "B",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-20T03:00:00+00:00",
                    "article_published_at": "2026-02-20T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "president_job_approval",
                    "option_name": "대통령 직무 긍정평가",
                    "value_mid": 48.0,
                    "pollster": "일반기사",
                    "survey_end_date": date(2026, 2, 20),
                    "source_grade": "A",
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-20T03:00:00+00:00",
                    "article_published_at": "2026-02-20T01:00:00+00:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
            ]

    def override_summary_repo():
        yield SummaryRepresentativeRepo()

    app.dependency_overrides[get_repository] = override_summary_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    body = res.json()

    assert [x["option_name"] for x in body["party_support"]] == ["국민의힘", "더불어민주당"]

    selected_dem = next(x for x in body["party_support"] if x["option_name"] == "더불어민주당")
    assert selected_dem["source_channel"] == "nesdc"
    assert selected_dem["selected_source_tier"] == "nesdc"
    assert selected_dem["value_mid"] == 34.0

    selected_kpp = next(x for x in body["party_support"] if x["option_name"] == "국민의힘")
    assert selected_kpp["pollster"] == "기사집계센터"
    assert selected_kpp["selected_source_tier"] == "article_aggregate"
    assert selected_kpp["value_mid"] == 39.0

    assert len(body["president_job_approval"]) == 1
    assert body["president_job_approval"][0]["value_mid"] == 48.0
    assert body["president_job_approval"][0]["selected_source_tier"] == "article"
    assert body["president_job_approval"][0]["selected_source_channel"] == "article"

    app.dependency_overrides.clear()


def test_regions_search_normalizes_non_ascii_and_encoded_query_forms():
    class CaptureRegionQueryRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.last_query = None
            self.last_has_data = None

        def search_regions(self, query, limit=20, has_data=None):
            self.last_query = query
            self.last_has_data = has_data
            return super().search_regions(query=query, limit=limit, has_data=has_data)

    repo = CaptureRegionQueryRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
    client = TestClient(app)

    # Double-encoded "서울": %25EC%2584%259C%25EC%259A%25B8
    double_encoded = client.get("/api/v1/regions/search?q=%25EC%2584%259C%25EC%259A%25B8")
    assert double_encoded.status_code == 200
    assert repo.last_query == "서울"

    nfd_seoul = unicodedata.normalize("NFD", "서울")
    nfd_query = client.get("/api/v1/regions/search", params={"q": nfd_seoul})
    assert nfd_query.status_code == 200
    assert repo.last_query == "서울"

    full_width_space = client.get("/api/v1/regions/search", params={"q": "  서울　특별시  "})
    assert full_width_space.status_code == 200
    assert repo.last_query == "서울 특별시"
    assert repo.last_has_data is None

    has_data_filtered = client.get("/api/v1/regions/search", params={"q": "서울", "has_data": "true"})
    assert has_data_filtered.status_code == 200
    assert repo.last_query == "서울"
    assert repo.last_has_data is True

    app.dependency_overrides.clear()


def test_regions_search_default_includes_official_no_data_regions():
    class OfficialRegionExposureRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.last_query = None
            self.last_has_data = None

        def search_regions(self, query, limit=20, has_data=None):
            self.last_query = query
            self.last_has_data = has_data
            rows = [
                {
                    "region_code": "29-000",
                    "sido_name": "세종특별자치시",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                    "has_data": False,
                    "matchup_count": 1,
                },
                {
                    "region_code": "42-000",
                    "sido_name": "강원특별자치도",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                    "has_data": False,
                    "matchup_count": 1,
                },
                {
                    "region_code": "11-000",
                    "sido_name": "서울특별시",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                    "has_data": True,
                    "matchup_count": 1,
                },
            ]
            if has_data is None:
                return rows[:limit]
            return [row for row in rows if row["has_data"] is has_data][:limit]

    repo = OfficialRegionExposureRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
    client = TestClient(app)

    baseline = client.get("/api/v1/regions/search")
    assert baseline.status_code == 200
    assert repo.last_query == ""
    assert repo.last_has_data is None
    codes = [row["region_code"] for row in baseline.json()]
    assert "29-000" in codes
    assert "42-000" in codes
    assert any(row["region_code"] == "29-000" and row["has_data"] is False for row in baseline.json())
    assert any(row["region_code"] == "42-000" and row["has_data"] is False for row in baseline.json())

    data_only = client.get("/api/v1/regions/search", params={"has_data": "true"})
    assert data_only.status_code == 200
    assert repo.last_query == ""
    assert repo.last_has_data is True
    assert [row["region_code"] for row in data_only.json()] == ["11-000"]

    app.dependency_overrides.clear()


def test_regions_search_normalizes_region_code_aliases_to_canonical_code():
    class CaptureRegionCodeRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.last_region_code = None
            self.last_query = None
            self.last_has_data = None

        def search_regions(self, query, limit=20, has_data=None):
            self.last_query = query
            self.last_has_data = has_data
            return super().search_regions(query=query, limit=limit, has_data=has_data)

        def search_regions_by_code(self, region_code, limit=20, has_data=None):
            self.last_region_code = region_code
            self.last_has_data = has_data
            return super().search_regions_by_code(region_code=region_code, limit=limit, has_data=has_data)

    repo = CaptureRegionCodeRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
    client = TestClient(app)

    alias_response = client.get("/api/v1/regions/search", params={"q": "KR-32"})
    assert alias_response.status_code == 200
    assert alias_response.json()[0]["region_code"] == "42-000"
    assert repo.last_region_code == "42-000"
    assert repo.last_query is None

    canonical_response = client.get("/api/v1/regions/search", params={"q": "42-000"})
    assert canonical_response.status_code == 200
    assert canonical_response.json() == alias_response.json()
    assert repo.last_region_code == "42-000"

    canonical_filtered = client.get("/api/v1/regions/search", params={"q": "42-000", "has_data": "true"})
    assert canonical_filtered.status_code == 200
    assert repo.last_region_code == "42-000"
    assert repo.last_has_data is True

    app.dependency_overrides.clear()


def test_region_elections_normalizes_region_code_aliases():
    class CaptureRegionElectionRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.last_region_code = None

        def fetch_region_elections(self, region_code, topology="official", version_id=None):
            self.last_region_code = region_code
            return super().fetch_region_elections(region_code, topology=topology, version_id=version_id)

    repo = CaptureRegionElectionRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
    client = TestClient(app)

    response = client.get("/api/v1/regions/KR-32/elections")
    assert response.status_code == 200
    assert response.json()[0]["region_code"] == "42-000"
    assert repo.last_region_code == "42-000"

    app.dependency_overrides.clear()


def test_matchup_normalizes_region_code_aliases_in_matchup_id():
    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    response = client.get("/api/v1/matchups/20260603|광역자치단체장|KR-32")
    assert response.status_code == 200
    assert response.json()["matchup_id"] == "20260603|광역자치단체장|42-000"

    app.dependency_overrides.clear()


def test_dashboard_summary_filters_rows_before_fixed_article_cutoff():
    class CutoffRepo(FakeApiRepo):
        def fetch_dashboard_summary(self, as_of):  # noqa: ARG002
            return [
                {
                    "option_type": "party_support",
                    "option_name": "신규정당",
                    "value_mid": 11.0,
                    "pollster": "테스트",
                    "survey_end_date": date(2026, 2, 18),
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2025-11-30T23:59:59+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "party_support",
                    "option_name": "기준통과정당",
                    "value_mid": 22.0,
                    "pollster": "테스트",
                    "survey_end_date": date(2026, 2, 18),
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2025-12-01T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
            ]

    def override_cutoff_repo():
        yield CutoffRepo()

    app.dependency_overrides[get_repository] = override_cutoff_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    names = [x["option_name"] for x in res.json()["party_support"]]
    assert names == ["기준통과정당"]

    app.dependency_overrides.clear()


def test_dashboard_summary_filters_rows_before_survey_end_cutoff():
    class SurveyEndCutoffRepo(FakeApiRepo):
        def fetch_dashboard_summary(self, as_of):  # noqa: ARG002
            return [
                {
                    "option_type": "party_support",
                    "option_name": "오래된조사정당",
                    "value_mid": 11.0,
                    "pollster": "테스트",
                    "survey_end_date": date(2025, 11, 30),
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-01-10T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
                {
                    "option_type": "party_support",
                    "option_name": "최신조사정당",
                    "value_mid": 22.0,
                    "pollster": "테스트",
                    "survey_end_date": date(2025, 12, 1),
                    "audience_scope": "national",
                    "audience_region_code": None,
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-01-10T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                    "verified": True,
                },
            ]

    def override_survey_end_cutoff_repo():
        yield SurveyEndCutoffRepo()

    app.dependency_overrides[get_repository] = override_survey_end_cutoff_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    names = [x["option_name"] for x in res.json()["party_support"]]
    assert names == ["최신조사정당"]

    app.dependency_overrides.clear()


def test_dashboard_big_matches_filters_rows_before_survey_end_cutoff():
    class BigMatchCutoffRepo(FakeApiRepo):
        def fetch_dashboard_big_matches(self, as_of, limit=3):  # noqa: ARG002
            rows = super().fetch_dashboard_big_matches(as_of=as_of, limit=limit)
            rows[0]["survey_end_date"] = date(2025, 11, 30)
            rows[0]["article_published_at"] = "2026-01-10T00:00:00+09:00"
            rows.append(
                {
                    "matchup_id": "20260603|기초자치단체장|11-010",
                    "title": "종로구청장 가상대결",
                    "survey_end_date": date(2025, 12, 1),
                    "value_mid": 38.0,
                    "spread": 2.1,
                    "audience_scope": "local",
                    "audience_region_code": "11-010",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-01-10T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                }
            )
            return rows

    def override_big_match_cutoff_repo():
        yield BigMatchCutoffRepo()

    app.dependency_overrides[get_repository] = override_big_match_cutoff_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/big-matches")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["matchup_id"] == "20260603|기초자치단체장|11-010"

    app.dependency_overrides.clear()


def test_map_latest_reason_counts_groups_cutoff_as_stale_cycle():
    class MapCutoffReasonRepo(FakeApiRepo):
        def fetch_dashboard_map_latest(self, as_of, limit=100):  # noqa: ARG002
            return [
                {
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "title": "서울시장 가상대결",
                    "value_mid": 44.0,
                    "survey_end_date": date(2025, 11, 30),
                    "option_name": "정원오",
                    "audience_scope": "regional",
                    "audience_region_code": "11-000",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-01-10T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-010",
                    "office_type": "기초자치단체장",
                    "title": "종로구청장 가상대결",
                    "value_mid": 41.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "오세훈",
                    "audience_scope": "local",
                    "audience_region_code": "11-010",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2025-11-30T23:59:59+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
                {
                    "region_code": "11-020",
                    "office_type": "기초자치단체장",
                    "title": "중구청장 가상대결",
                    "value_mid": 42.0,
                    "survey_end_date": date(2026, 2, 18),
                    "option_name": "박형준",
                    "audience_scope": "local",
                    "audience_region_code": "11-020",
                    "observation_updated_at": "2026-02-18T03:00:00+00:00",
                    "article_published_at": "2026-01-10T00:00:00+09:00",
                    "source_channel": "article",
                    "source_channels": ["article"],
                },
            ][:limit]

    def override_map_cutoff_reason_repo():
        yield MapCutoffReasonRepo()

    app.dependency_overrides[get_repository] = override_map_cutoff_reason_repo
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/map-latest")
    assert res.status_code == 200
    body = res.json()
    assert body["filter_stats"]["reason_counts"]["stale_cycle"] == 2
    assert body["filter_stats"]["kept_count"] == 1
    assert body["items"][0]["option_name"] == "박형준"

    app.dependency_overrides.clear()


def test_matchup_before_cutoff_returns_not_found():
    class CutoffMatchupRepo(FakeApiRepo):
        def get_matchup(self, matchup_id):  # noqa: ARG002
            row = super().get_matchup("anything")
            row["source_channel"] = "article"
            row["source_channels"] = ["article"]
            row["article_published_at"] = "2025-11-30T23:59:59+09:00"
            return row

    def override_cutoff_matchup_repo():
        yield CutoffMatchupRepo()

    app.dependency_overrides[get_repository] = override_cutoff_matchup_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/matchups/20260603|광역자치단체장|11-000")
    assert res.status_code == 404

    app.dependency_overrides.clear()


def test_matchup_with_survey_end_before_cutoff_returns_not_found():
    class CutoffSurveyMatchupRepo(FakeApiRepo):
        def get_matchup(self, matchup_id):  # noqa: ARG002
            row = super().get_matchup("anything")
            row["survey_end_date"] = date(2025, 11, 30)
            row["source_channel"] = "article"
            row["source_channels"] = ["article"]
            row["article_published_at"] = "2026-01-10T00:00:00+09:00"
            return row

    def override_cutoff_survey_matchup_repo():
        yield CutoffSurveyMatchupRepo()

    app.dependency_overrides[get_repository] = override_cutoff_survey_matchup_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/matchups/20260603|광역자치단체장|11-000")
    assert res.status_code == 404

    app.dependency_overrides.clear()


def test_region_elections_topology_scenario_query_contract():
    class ScenarioRepo(FakeApiRepo):
        def fetch_region_elections(self, region_code, topology="official", version_id=None):  # noqa: ARG002
            row = super().fetch_region_elections(region_code, topology=topology, version_id=version_id)[0]
            row["region_code"] = "29-46-000"
            row["title"] = "광주·전남 통합시장 가상대결"
            row["has_poll_data"] = False
            row["has_candidate_data"] = False
            row["latest_survey_end_date"] = None
            row["latest_matchup_id"] = None
            row["status"] = "조사 데이터 없음"
            row["is_placeholder"] = True
            return [row]

    def override_scenario_repo():
        yield ScenarioRepo()

    app.dependency_overrides[get_repository] = override_scenario_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get(
        "/api/v1/regions/29-000/elections",
        params={"topology": "scenario", "version_id": "scenario-gj-jn-merge-v1"},
    )
    assert res.status_code == 200
    row = res.json()[0]
    assert row["topology"] == "scenario"
    assert row["topology_version_id"] == "scenario-gj-jn-merge-v1"
    assert row["region_code"] == "29-46-000"
    assert row["status"] == "조사 데이터 없음"
    assert row["is_placeholder"] is True

    app.dependency_overrides.clear()


def test_matchup_option_candidate_id_key_is_present_even_when_value_is_null():
    class NullableCandidateRepo(FakeApiRepo):
        def get_matchup(self, matchup_id):  # noqa: ARG002
            row = super().get_matchup("20260603|광역자치단체장|11-000")
            row["options"][0]["candidate_id"] = None
            row["scenarios"][0]["options"][0]["candidate_id"] = None
            return row

    def override_nullable_candidate_repo():
        yield NullableCandidateRepo()

    app.dependency_overrides[get_repository] = override_nullable_candidate_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/matchups/20260603|광역자치단체장|11-000")
    assert res.status_code == 200
    body = res.json()
    assert "candidate_id" in body["options"][0]
    assert body["options"][0]["candidate_id"] is None
    assert "candidate_id" in body["scenarios"][0]["options"][0]
    assert body["scenarios"][0]["options"][0]["candidate_id"] is None

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


def test_dashboard_quality_empty_safe_contract():
    class QualityRepo(FakeApiRepo):
        def fetch_dashboard_quality(self):
            return {
                "quality_status": "warn",
                "freshness_p50_hours": None,
                "freshness_p90_hours": None,
                "official_confirmed_ratio": 0.0,
                "needs_manual_review_count": 0,
                "source_channel_mix": {"article_ratio": 0.0, "nesdc_ratio": 0.0},
                "freshness": {
                    "p50_hours": None,
                    "p90_hours": None,
                    "over_24h_ratio": 0.0,
                    "over_48h_ratio": 0.0,
                    "status": "warn",
                },
                "official_confirmation": {
                    "confirmed_ratio": 0.0,
                    "unconfirmed_count": 0,
                    "status": "critical",
                },
                "review_queue": {
                    "pending_count": 0,
                    "in_progress_count": 0,
                    "pending_over_24h_count": 0,
                },
            }

    def override_quality_repo():
        yield QualityRepo()

    app.dependency_overrides[get_repository] = override_quality_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/dashboard/quality")
    assert res.status_code == 200
    body = res.json()
    assert body["freshness_p50_hours"] is None
    assert body["freshness_p90_hours"] is None
    assert body["official_confirmed_ratio"] == 0.0
    assert body["needs_manual_review_count"] == 0
    assert body["source_channel_mix"] == {"article_ratio": 0.0, "nesdc_ratio": 0.0}
    assert body["quality_status"] == "warn"
    assert body["freshness"]["status"] == "warn"
    assert body["official_confirmation"]["status"] == "critical"
    assert body["review_queue"]["pending_count"] == 0

    app.dependency_overrides.clear()


def test_review_decision_endpoints_require_token_and_update_status(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.setenv("DATA_GO_KR_KEY", "test-data-go-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "dev-internal-token")
    get_settings.cache_clear()

    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    payload = {"assigned_to": "ops.user", "review_note": "검수 승인"}

    missing = client.post("/api/v1/review/101/approve", json=payload)
    assert missing.status_code == 401

    invalid = client.post(
        "/api/v1/review/101/approve",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert invalid.status_code == 403

    approved = client.post(
        "/api/v1/review/101/approve",
        json=payload,
        headers={"Authorization": "Bearer dev-internal-token"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["id"] == 101
    assert body["status"] == "approved"
    assert body["assigned_to"] == "ops.user"
    assert body["review_note"] == "검수 승인"

    rejected = client.post(
        "/api/v1/review/100/reject",
        json={"review_note": "근거 부족"},
        headers={"Authorization": "Bearer dev-internal-token"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["id"] == 100
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["review_note"] == "근거 부족"

    missing_item = client.post(
        "/api/v1/review/999/approve",
        json={},
        headers={"Authorization": "Bearer dev-internal-token"},
    )
    assert missing_item.status_code == 404

    app.dependency_overrides.clear()
    get_settings.cache_clear()


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


def test_run_ingest_normalizes_candidate_payload_before_validation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.setenv("DATA_GO_KR_KEY", "test-data-go-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "dev-internal-token")
    get_settings.cache_clear()

    class CaptureCandidateRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.captured_candidates: list[dict] = []
            self.captured_observations: list[dict] = []

        def upsert_candidate(self, candidate):
            self.captured_candidates.append(candidate)
            return None

        def upsert_poll_observation(self, observation, article_id, ingestion_run_id):
            self.captured_observations.append(observation)
            return 1

    repo = CaptureCandidateRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
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
                "candidates": [
                    {
                        "candidate_id": "cand-1",
                        "name_ko": "홍길동",
                        "party_name": None,
                        "party_inferred": "더불어민주당",
                        "party_inference_source": "data_go_candidate_api_region",
                    }
                ],
                "observation": {
                    "observation_key": "obs-220",
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "20260603|광역자치단체장|11-000",
                    "audience_scope": "nationwide",
                    "audience_region_code": "11-000",
                    "margin_of_error": "±3.1%p",
                },
                "options": [
                    {"option_type": "candidate", "option_name": "홍길동", "value_raw": "51%"}
                ],
            }
        ],
    }

    response = client.post(
        "/api/v1/jobs/run-ingest",
        json=payload,
        headers={"Authorization": "Bearer dev-internal-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert repo.captured_candidates
    assert repo.captured_candidates[0]["party_inferred"] is True
    assert repo.captured_candidates[0]["party_name"] == "더불어민주당"
    assert repo.captured_candidates[0]["party_inference_source"] == "manual"
    assert repo.captured_observations
    assert repo.captured_observations[0]["audience_scope"] == "national"
    assert repo.captured_observations[0]["audience_region_code"] is None
    assert repo.captured_observations[0]["margin_of_error"] == 3.1

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_run_ingest_normalizes_presidential_option_type_and_routes_ambiguous_review(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    monkeypatch.setenv("DATA_GO_KR_KEY", "test-data-go-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", "dev-internal-token")
    get_settings.cache_clear()

    class CaptureOptionRepo(FakeApiRepo):
        def __init__(self):
            super().__init__()
            self.captured_options: list[dict] = []
            self.captured_review: list[tuple[str, str, str, str]] = []

        def upsert_poll_option(self, observation_id, option):  # noqa: ARG002
            self.captured_options.append(option)
            return None

        def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
            self.captured_review.append((entity_type, entity_id, issue_type, review_note))
            return None

    repo = CaptureOptionRepo()

    def override_capture_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_capture_repo
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
                    "observation_key": "obs-282",
                    "survey_name": "survey",
                    "pollster": "MBC",
                    "region_code": "11-000",
                    "office_type": "광역자치단체장",
                    "matchup_id": "20260603|광역자치단체장|11-000",
                },
                "options": [
                    {"option_type": "presidential_approval", "option_name": "국정안정론", "value_raw": "53~55%"},
                    {
                        "option_type": "presidential_approval",
                        "option_name": "국정안정 긍정평가",
                        "value_raw": "44%",
                    },
                ],
            }
        ],
    }

    response = client.post(
        "/api/v1/jobs/run-ingest",
        json=payload,
        headers={"Authorization": "Bearer dev-internal-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert repo.captured_options
    option_types = [row["option_type"] for row in repo.captured_options]
    assert "election_frame" in option_types
    assert "presidential_approval" in option_types
    ambiguous = next(row for row in repo.captured_options if row["option_name"] == "국정안정 긍정평가")
    assert ambiguous["needs_manual_review"] is True
    assert any(row[2] == "mapping_error" for row in repo.captured_review)

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_cors_allows_public_web_origin():
    client = TestClient(app)
    res = client.options(
        "/health",
        headers={
            "Origin": "https://2026-deploy.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://2026-deploy.vercel.app"


def test_cors_rejects_unknown_origin():
    client = TestClient(app)
    res = client.options(
        "/health",
        headers={
            "Origin": "https://malicious.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 400
    assert res.headers.get("access-control-allow-origin") is None


def test_health_db_ok(monkeypatch: pytest.MonkeyPatch):
    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def execute(self, query):  # noqa: ARG002
            return None

        def fetchone(self):
            return {"ok": 1}

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def cursor(self):
            return _Cursor()

    from contextlib import contextmanager

    @contextmanager
    def _fake_get_connection():
        yield _Conn()

    monkeypatch.setattr("app.main.get_connection", _fake_get_connection)

    client = TestClient(app)
    res = client.get("/health/db")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["ping"] is True


def test_health_db_reports_degraded_when_db_is_not_configured(monkeypatch: pytest.MonkeyPatch):
    from contextlib import contextmanager

    from app.db import DatabaseConfigurationError

    @contextmanager
    def _fake_get_connection():
        raise DatabaseConfigurationError("DATABASE_URL is empty")
        yield  # pragma: no cover

    monkeypatch.setattr("app.main.get_connection", _fake_get_connection)

    client = TestClient(app)
    res = client.get("/health/db")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["reason"] == "database_not_configured"


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
    assert "party_inferred" in body
    assert "party_inference_source" in body
    assert "party_inference_confidence" in body
    assert "needs_manual_review" in body
    assert "source_priority" in body
    assert "freshness_hours" in body
    assert "official_release_at" in body
    assert "article_published_at" in body
    assert "is_official_confirmed" in body
    assert body["profile_source"] == "mixed"
    assert body["profile_provenance"]["party_name"] == "data_go"
    assert body["profile_provenance"]["job"] == "data_go"
    assert body["profile_provenance"]["career_summary"] == "ingest"
    assert body["profile_completeness"] == "complete"

    app.dependency_overrides.clear()


def test_candidate_endpoint_falls_back_name_when_missing():
    class MissingNameRepo(FakeApiRepo):
        def get_candidate(self, candidate_id):
            row = super().get_candidate(candidate_id)
            row["name_ko"] = "   "
            row["party_name"] = " "
            return row

    app.dependency_overrides[get_repository] = lambda: MissingNameRepo()
    app.dependency_overrides[get_candidate_data_go_service] = override_candidate_data_go_service
    client = TestClient(app)

    res = client.get("/api/v1/candidates/cand-jwo")
    assert res.status_code == 200
    body = res.json()
    assert body["name_ko"] == "cand-jwo"
    assert body["party_name"] is None
    assert body["placeholder_name_applied"] is True
    assert body["profile_completeness"] == "partial"
    assert body["profile_provenance"]["party_name"] == "missing"

    app.dependency_overrides.clear()


def test_candidate_endpoint_handles_profile_missing_contract_with_nulls():
    class SparseCandidateRepo(FakeApiRepo):
        def get_candidate(self, candidate_id):
            row = super().get_candidate(candidate_id)
            row["party_name"] = None
            row["career_summary"] = None
            row["election_history"] = None
            row["job"] = "  "
            row["gender"] = "  "
            row["name_ko"] = "   "
            row["profile_source_type"] = None
            row["profile_source_url"] = "  "
            return row

    app.dependency_overrides[get_repository] = lambda: SparseCandidateRepo()
    app.dependency_overrides[get_candidate_data_go_service] = lambda: FakeCandidateDataGoService({})
    client = TestClient(app)

    res = client.get("/api/v1/candidates/cand-jwo")
    assert res.status_code == 200
    body = res.json()
    assert body["name_ko"] == "cand-jwo"
    assert body["placeholder_name_applied"] is True
    assert body["party_name"] is None
    assert body["job"] is None
    assert body["gender"] is None
    assert body["career_summary"] is None
    assert body["election_history"] is None
    assert body["profile_source"] == "ingest"
    assert body["profile_completeness"] == "empty"
    assert body["profile_source_type"] is None
    assert body["profile_source_url"] is None
    assert body["profile_provenance"]["party_name"] == "missing"
    assert body["profile_provenance"]["career_summary"] == "missing"
    assert body["profile_provenance"]["election_history"] == "missing"
    assert body["profile_provenance"]["birth_date"] == "ingest"

    app.dependency_overrides.clear()
