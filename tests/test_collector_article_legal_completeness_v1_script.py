from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_collector_article_legal_completeness_v1_batch50 import (
    generate_collector_article_legal_completeness_v1_batch50,
)


def _record(
    *,
    key: str,
    pollster: str | None,
    survey_end_date: str | None,
    sample_size: int | None,
    response_rate: float | None,
    margin_of_error: float | None,
    raw_text: str,
) -> dict:
    return {
        "article": {
            "url": f"https://example.test/{key}",
            "title": "기사",
            "publisher": "테스트",
            "published_at": "2026-02-20T09:00:00+09:00",
            "raw_text": raw_text,
            "raw_hash": key,
        },
        "region": {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
        "candidates": [],
        "observation": {
            "observation_key": key,
            "survey_name": "조사",
            "pollster": pollster,
            "survey_start_date": None,
            "survey_end_date": survey_end_date,
            "sample_size": sample_size,
            "response_rate": response_rate,
            "margin_of_error": margin_of_error,
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "matchup_id": "20260603|광역자치단체장|11-000",
            "verified": False,
            "source_grade": None,
        },
        "options": [],
    }


def test_completeness_threshold_routes_review_queue(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_bootstrap",
        "extractor_version": "x",
        "llm_model": None,
        "records": [
            _record(
                key="obs-good",
                pollster="한국갤럽",
                survey_end_date="2026-02-20",
                sample_size=1000,
                response_rate=12.3,
                margin_of_error=3.1,
                raw_text="의뢰자: 서울신문",
            ),
            _record(
                key="obs-bad",
                pollster=None,
                survey_end_date=None,
                sample_size=None,
                response_rate=None,
                margin_of_error=None,
                raw_text="의뢰 정보 없음",
            ),
        ],
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = generate_collector_article_legal_completeness_v1_batch50(
        source_path=str(source),
        sample_size=2,
        threshold=0.8,
    )

    assert out["report"]["completeness"]["threshold_miss_count"] == 1
    assert len(out["review_queue_candidates"]) == 1
    assert out["review_queue_candidates"][0]["error_code"] == "LEGAL_COMPLETENESS_BELOW_THRESHOLD"


def test_completeness_schema_injection_and_reason_codes(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_bootstrap",
        "extractor_version": "x",
        "llm_model": None,
        "records": [
            _record(
                key="obs-1",
                pollster="한국갤럽",
                survey_end_date="2026-02-20",
                sample_size=1000,
                response_rate=12.3,
                margin_of_error=3.1,
                raw_text="의뢰자: 서울신문",
            ),
            _record(
                key="obs-2",
                pollster="리얼미터",
                survey_end_date="2026-02-20",
                sample_size=1000,
                response_rate=200.0,
                margin_of_error=3.1,
                raw_text="의뢰자: 부산일보",
            ),
        ],
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = generate_collector_article_legal_completeness_v1_batch50(
        source_path=str(source),
        sample_size=2,
        threshold=0.8,
    )

    rec1 = out["batch"]["records"][0]["observation"]
    rec2 = out["batch"]["records"][1]["observation"]

    assert rec1["legal_completeness_score"] == 1.0
    assert rec1["legal_reason_code"] == "COMPLETE"
    assert rec1["legal_required_schema"]["sponsor"]["is_present"] is True

    assert rec2["legal_reason_code"] == "ABNORMAL_REQUIRED_FIELD_VALUE"
    assert "response_rate" in rec2["legal_invalid_fields"]
