#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REPORT_PATH="data/qa_api_contract_report.json"

usage() {
  cat <<USAGE
Usage: $0 [--report <path>]

Runs API 12-endpoint contract suite with success/failure/empty/auth-failure cases.
Writes JSON report (default: data/qa_api_contract_report.json).
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report)
      REPORT_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[FAIL] .venv python not found: $PYTHON_BIN"
  exit 1
fi

"$PYTHON_BIN" - "$REPORT_PATH" <<'PY'
from __future__ import annotations

import json
import os
import platform
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository
from app.config import get_settings
from app.main import app


class FakeRepo:
    def __init__(self, mode: str = "success"):
        self.mode = mode
        self._run_id = 0

    def _maybe_fail(self):
        if self.mode == "failure":
            raise RuntimeError("forced repository error")

    def fetch_dashboard_summary(self, as_of):
        self._maybe_fail()
        if self.mode == "empty":
            return []
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
                "option_type": "presidential_approval",
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
        ]

    def fetch_dashboard_map_latest(self, as_of, limit=100):
        self._maybe_fail()
        if self.mode == "empty":
            return []
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
        self._maybe_fail()
        if self.mode == "empty":
            return []
        return [
            {
                "matchup_id": "20260603|광역자치단체장|11-000",
                "title": "서울시장 가상대결",
                "survey_end_date": date(2026, 2, 18),
                "value_mid": 44.0,
                "spread": 2.0,
            }
        ]

    def search_regions(self, query, limit=20):
        self._maybe_fail()
        if self.mode == "empty":
            return []
        return [
            {
                "region_code": "11-000",
                "sido_name": "서울특별시",
                "sigungu_name": "전체",
                "admin_level": "sido",
            }
        ]

    def fetch_region_elections(self, region_code):
        self._maybe_fail()
        if self.mode == "empty":
            return []
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
        self._maybe_fail()
        if matchup_id == "missing":
            return None
        if self.mode == "empty":
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
            "observation_updated_at": "2026-02-18T03:00:00+00:00",
            "article_published_at": "2026-02-18T01:00:00+00:00",
            "official_release_at": None,
            "source_channel": "article",
            "source_channels": ["article", "nesdc"],
            "verified": True,
            "options": [
                {
                    "option_name": "정원오",
                    "value_mid": 44.0,
                    "value_raw": "44%",
                    "party_inferred": True,
                    "party_inference_source": "name_rule",
                    "party_inference_confidence": 0.91,
                    "needs_manual_review": False,
                },
                {
                    "option_name": "오세훈",
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
        self._maybe_fail()
        if candidate_id == "missing":
            return None
        if self.mode == "empty":
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
        self._maybe_fail()
        if self.mode == "empty":
            return []
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

    def fetch_ops_coverage_summary(self):
        self._maybe_fail()
        if self.mode == "partial":
            return {
                "state": "partial",
                "warning_message": "Coverage partial: 6/11 regions covered.",
                "regions_total": 11,
                "regions_covered": 6,
                "sido_covered": 6,
                "observations_total": 40,
                "latest_survey_end_date": date(2026, 2, 18),
            }
        if self.mode == "empty":
            return {
                "state": "empty",
                "warning_message": "No observations ingested yet.",
                "regions_total": 11,
                "regions_covered": 0,
                "sido_covered": 0,
                "observations_total": 0,
                "latest_survey_end_date": None,
            }
        return {
            "state": "ready",
            "warning_message": None,
            "regions_total": 11,
            "regions_covered": 11,
            "sido_covered": 6,
            "observations_total": 100,
            "latest_survey_end_date": date(2026, 2, 19),
        }

    def fetch_review_queue_stats(self, *, window_hours=24):  # noqa: ARG002
        self._maybe_fail()
        if self.mode == "empty":
            return {
                "total_count": 0,
                "pending_count": 0,
                "in_progress_count": 0,
                "resolved_count": 0,
                "issue_type_counts": [],
                "error_code_counts": [],
            }
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
        self._maybe_fail()
        if self.mode == "empty":
            return []
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


def override_repo(repo: FakeRepo):
    def _dep():
        yield repo

    return _dep


def make_client(repo: FakeRepo, raise_server_exceptions: bool = True) -> TestClient:
    app.dependency_overrides[get_repository] = override_repo(repo)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def assert_keys(obj: dict, keys: list[str]):
    for key in keys:
        assert key in obj, f"missing key: {key}"


def main() -> int:
    report_path = Path(sys.argv[1])
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Internal auth endpoint depends on settings values.
    os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    os.environ.setdefault("DATA_GO_KR_KEY", "test-data-go-key")
    os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")
    os.environ.setdefault("INTERNAL_JOB_TOKEN", "dev-internal-token")
    get_settings.cache_clear()

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

    cases: list[dict] = []

    def run_case(name: str, category: str, endpoint: str, fn):
        started = datetime.now(timezone.utc)
        status = "pass"
        error = None
        details = None
        try:
            details = fn()
        except Exception as exc:  # noqa: BLE001
            status = "fail"
            tb = traceback.format_exc(limit=3)
            error = f"{type(exc).__name__}: {exc}"
            details = tb
        finally:
            app.dependency_overrides.clear()

        cases.append(
            {
                "name": name,
                "category": category,
                "endpoint": endpoint,
                "status": status,
                "error": error,
                "details": details,
                "executed_at": started.isoformat(),
            }
        )

    # success cases
    run_case(
        "summary_success",
        "success",
        "GET /api/v1/dashboard/summary",
        lambda: (
            lambda r: (
                assert_keys(r.json(), ["party_support", "presidential_approval", "scope_breakdown"]),
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                len(r.json().get("party_support", [])) >= 1
                or (_ for _ in ()).throw(AssertionError("party_support empty")),
                assert_keys(
                    r.json()["party_support"][0],
                    [
                        "audience_scope",
                        "audience_region_code",
                        "source_channel",
                        "source_channels",
                        "source_priority",
                        "freshness_hours",
                        "official_release_at",
                        "article_published_at",
                        "is_official_confirmed",
                    ],
                ),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/dashboard/summary")),
    )

    run_case(
        "map_latest_success",
        "success",
        "GET /api/v1/dashboard/map-latest",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                len(r.json().get("items", [])) >= 1 or (_ for _ in ()).throw(AssertionError("items empty")),
                assert_keys(
                    r.json()["items"][0],
                    ["audience_scope", "audience_region_code", "source_channel", "source_channels"],
                ),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/dashboard/map-latest")),
    )

    run_case(
        "big_matches_success",
        "success",
        "GET /api/v1/dashboard/big-matches",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                len(r.json().get("items", [])) >= 1 or (_ for _ in ()).throw(AssertionError("items empty")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/dashboard/big-matches")),
    )

    run_case(
        "regions_search_success",
        "success",
        "GET /api/v1/regions/search",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                isinstance(r.json(), list) or (_ for _ in ()).throw(AssertionError("not list")),
                len(r.json()) >= 1 or (_ for _ in ()).throw(AssertionError("empty")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/regions/search", params={"q": "서울"})),
    )

    run_case(
        "region_elections_success",
        "success",
        "GET /api/v1/regions/{region_code}/elections",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                isinstance(r.json(), list) or (_ for _ in ()).throw(AssertionError("not list")),
                len(r.json()) >= 1 or (_ for _ in ()).throw(AssertionError("empty")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/regions/11-000/elections")),
    )

    run_case(
        "matchup_success",
        "success",
        "GET /api/v1/matchups/{matchup_id}",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                assert_keys(r.json(), ["matchup_id", "options"]),
                len(r.json().get("options", [])) >= 1
                or (_ for _ in ()).throw(AssertionError("options empty")),
                assert_keys(
                    r.json(),
                    [
                        "audience_scope",
                        "audience_region_code",
                        "source_channel",
                        "source_channels",
                        "source_priority",
                        "freshness_hours",
                        "official_release_at",
                        "article_published_at",
                        "is_official_confirmed",
                    ],
                ),
                assert_keys(
                    r.json()["options"][0],
                    [
                        "party_inferred",
                        "party_inference_source",
                        "party_inference_confidence",
                        "needs_manual_review",
                    ],
                ),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/matchups/20260603|광역자치단체장|11-000")),
    )

    run_case(
        "candidate_success",
        "success",
        "GET /api/v1/candidates/{candidate_id}",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                assert_keys(
                    r.json(),
                    [
                        "candidate_id",
                        "name_ko",
                        "party_name",
                        "party_inferred",
                        "party_inference_source",
                        "party_inference_confidence",
                        "needs_manual_review",
                        "source_channel",
                        "source_channels",
                        "source_priority",
                        "freshness_hours",
                        "official_release_at",
                        "article_published_at",
                        "is_official_confirmed",
                    ],
                ),
                isinstance(r.json().get("party_inferred"), bool)
                or (_ for _ in ()).throw(AssertionError("party_inferred type mismatch")),
                isinstance(r.json().get("needs_manual_review"), bool)
                or (_ for _ in ()).throw(AssertionError("needs_manual_review type mismatch")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/candidates/cand-jwo")),
    )

    run_case(
        "review_queue_items_success",
        "success",
        "GET /api/v1/review-queue/items",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                isinstance(r.json(), list) or (_ for _ in ()).throw(AssertionError("not list")),
                len(r.json()) >= 1 or (_ for _ in ()).throw(AssertionError("empty")),
            )
        )(
            make_client(FakeRepo("success")).get(
                "/api/v1/review-queue/items",
                params={"status": "pending"},
            )
        ),
    )

    run_case(
        "ops_coverage_summary_success",
        "success",
        "GET /api/v1/ops/coverage/summary",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                assert_keys(
                    r.json(),
                    [
                        "state",
                        "warning_message",
                        "regions_total",
                        "regions_covered",
                        "sido_covered",
                        "observations_total",
                        "latest_survey_end_date",
                    ],
                ),
                r.json().get("state") == "ready"
                or (_ for _ in ()).throw(AssertionError(f"unexpected state={r.json().get('state')}")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/ops/coverage/summary")),
    )

    run_case(
        "ops_coverage_summary_partial",
        "partial",
        "GET /api/v1/ops/coverage/summary",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("state") == "partial"
                or (_ for _ in ()).throw(AssertionError(f"unexpected state={r.json().get('state')}")),
                isinstance(r.json().get("warning_message"), str)
                or (_ for _ in ()).throw(AssertionError("warning_message should be string")),
            )
        )(make_client(FakeRepo("partial")).get("/api/v1/ops/coverage/summary")),
    )

    run_case(
        "review_queue_stats_success",
        "success",
        "GET /api/v1/review-queue/stats",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                assert_keys(r.json(), ["total_count", "issue_type_counts", "error_code_counts"]),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/review-queue/stats", params={"window_hours": 48})),
    )

    run_case(
        "review_queue_trends_success",
        "success",
        "GET /api/v1/review-queue/trends",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                assert_keys(r.json(), ["bucket_hours", "points"]),
            )
        )(
            make_client(FakeRepo("success")).get(
                "/api/v1/review-queue/trends",
                params={"window_hours": 24, "bucket_hours": 6},
            )
        ),
    )

    run_case(
        "run_ingest_success",
        "success",
        "POST /api/v1/jobs/run-ingest",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("status") == "success"
                or (_ for _ in ()).throw(AssertionError(f"status_field={r.json().get('status')}")),
            )
        )(
            make_client(FakeRepo("success")).post(
                "/api/v1/jobs/run-ingest",
                json=payload,
                headers={"Authorization": "Bearer dev-internal-token"},
            )
        ),
    )

    # empty-data cases
    run_case(
        "summary_empty",
        "empty",
        "GET /api/v1/dashboard/summary",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("party_support") == [] or (_ for _ in ()).throw(AssertionError("party_support not empty")),
                r.json().get("presidential_approval") == []
                or (_ for _ in ()).throw(AssertionError("presidential_approval not empty")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/dashboard/summary")),
    )

    run_case(
        "regions_search_empty",
        "empty",
        "GET /api/v1/regions/search",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json() == [] or (_ for _ in ()).throw(AssertionError("expected []")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/regions/search", params={"q": "서울"})),
    )

    run_case(
        "map_latest_empty",
        "empty",
        "GET /api/v1/dashboard/map-latest",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("items") == [] or (_ for _ in ()).throw(AssertionError("expected empty items")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/dashboard/map-latest")),
    )

    run_case(
        "big_matches_empty",
        "empty",
        "GET /api/v1/dashboard/big-matches",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("items") == [] or (_ for _ in ()).throw(AssertionError("expected empty items")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/dashboard/big-matches")),
    )

    run_case(
        "region_elections_empty",
        "empty",
        "GET /api/v1/regions/{region_code}/elections",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json() == [] or (_ for _ in ()).throw(AssertionError("expected []")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/regions/11-000/elections")),
    )

    run_case(
        "review_queue_items_empty",
        "empty",
        "GET /api/v1/review-queue/items",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json() == [] or (_ for _ in ()).throw(AssertionError("expected []")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/review-queue/items")),
    )

    run_case(
        "ops_coverage_summary_empty",
        "empty",
        "GET /api/v1/ops/coverage/summary",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("state") == "empty"
                or (_ for _ in ()).throw(AssertionError(f"unexpected state={r.json().get('state')}")),
                r.json().get("regions_covered") == 0
                or (_ for _ in ()).throw(AssertionError("expected regions_covered=0")),
                r.json().get("sido_covered") == 0 or (_ for _ in ()).throw(AssertionError("expected sido_covered=0")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/ops/coverage/summary")),
    )

    run_case(
        "review_queue_stats_empty",
        "empty",
        "GET /api/v1/review-queue/stats",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("total_count") == 0 or (_ for _ in ()).throw(AssertionError("expected total_count=0")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/review-queue/stats")),
    )

    run_case(
        "review_queue_trends_empty",
        "empty",
        "GET /api/v1/review-queue/trends",
        lambda: (
            lambda r: (
                r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
                r.json().get("points") == [] or (_ for _ in ()).throw(AssertionError("expected empty points")),
            )
        )(make_client(FakeRepo("empty")).get("/api/v1/review-queue/trends")),
    )

    # auth-failure cases
    run_case(
        "run_ingest_auth_missing",
        "auth_failure",
        "POST /api/v1/jobs/run-ingest",
        lambda: (
            lambda r: (
                r.status_code == 401 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(make_client(FakeRepo("success")).post("/api/v1/jobs/run-ingest", json=payload)),
    )

    run_case(
        "run_ingest_auth_invalid",
        "auth_failure",
        "POST /api/v1/jobs/run-ingest",
        lambda: (
            lambda r: (
                r.status_code == 403 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(
            make_client(FakeRepo("success")).post(
                "/api/v1/jobs/run-ingest",
                json=payload,
                headers={"Authorization": "Bearer wrong-token"},
            )
        ),
    )

    # failure cases
    run_case(
        "summary_internal_error_500",
        "failure",
        "GET /api/v1/dashboard/summary",
        lambda: (
            lambda r: (
                r.status_code == 500 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(make_client(FakeRepo("failure"), raise_server_exceptions=False).get("/api/v1/dashboard/summary")),
    )

    run_case(
        "candidate_not_found_404",
        "failure",
        "GET /api/v1/candidates/{candidate_id}",
        lambda: (
            lambda r: (
                r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/candidates/missing")),
    )

    run_case(
        "matchup_not_found_404",
        "failure",
        "GET /api/v1/matchups/{matchup_id}",
        lambda: (
            lambda r: (
                r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(make_client(FakeRepo("success")).get("/api/v1/matchups/missing")),
    )

    run_case(
        "run_ingest_invalid_payload_422",
        "failure",
        "POST /api/v1/jobs/run-ingest",
        lambda: (
            lambda r: (
                r.status_code == 422 or (_ for _ in ()).throw(AssertionError(f"status={r.status_code}")),
            )
        )(
            make_client(FakeRepo("success")).post(
                "/api/v1/jobs/run-ingest",
                json={"run_type": "manual", "extractor_version": "manual-v1"},
                headers={"Authorization": "Bearer dev-internal-token"},
            )
        ),
    )

    total = len(cases)
    passed = sum(1 for c in cases if c["status"] == "pass")
    failed = total - passed

    by_category: dict[str, dict[str, int]] = {}
    for case in cases:
        cat = case["category"]
        bucket = by_category.setdefault(cat, {"total": 0, "pass": 0, "fail": 0})
        bucket["total"] += 1
        bucket["pass" if case["status"] == "pass" else "fail"] += 1

    report = {
        "suite": "qa_api_contract_suite",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "summary": {
            "total": total,
            "pass": passed,
            "fail": failed,
            "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        },
        "by_category": by_category,
        "cases": cases,
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report written: {report_path}")
    print(f"summary: total={total}, pass={passed}, fail={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
