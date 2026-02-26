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
    sponsor: str | None,
    survey_end_date: str | None,
    sample_size: int | None,
    method: str | None,
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
            "sponsor": sponsor,
            "method": method,
            "region_code": "11-000",
            "office_type": "광역자치단체장",
            "matchup_id": "20260603|광역자치단체장|11-000",
            "verified": False,
            "source_grade": None,
        },
        "options": [],
    }


def test_legal_required_fields_routes_missing_and_tracks_missing_reason(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_bootstrap",
        "extractor_version": "x",
        "llm_model": None,
        "records": [
            _record(
                key="obs-good",
                pollster="한국갤럽",
                sponsor="서울신문",
                survey_end_date="2026-02-20",
                sample_size=1000,
                method="전화면접조사",
                response_rate=12.3,
                margin_of_error=3.1,
                raw_text="의뢰기관 서울신문 조사기관 한국갤럽 표본수 1,000명 응답률 12.3% 오차범위 ±3.1%p 95% 신뢰수준",
            ),
            _record(
                key="obs-bad",
                pollster=None,
                sponsor=None,
                survey_end_date=None,
                sample_size=None,
                method=None,
                response_rate=None,
                margin_of_error=None,
                raw_text="관련 정보 없음",
            ),
        ],
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = generate_collector_article_legal_completeness_v1_batch50(
        source_path=str(source),
        sample_size=2,
        threshold=0.9,
        eval_sample_size=2,
    )

    assert out["report"]["completeness"]["threshold_miss_count"] == 1
    assert len(out["review_queue_candidates"]) == 1
    assert out["review_queue_candidates"][0]["error_code"] == "LEGAL_REQUIRED_FIELDS_NEEDS_REVIEW"
    assert out["report"]["acceptance_checks"]["missing_reason_coverage_eq_100"] is True

    bad_obs = out["batch"]["records"][1]["observation"]
    sponsor_schema = bad_obs["legal_required_schema"]["sponsor"]
    assert sponsor_schema["missing_reason"] == "actor_not_found"
    assert sponsor_schema["extraction_confidence"] == 0.0


def test_legal_required_fields_routes_conflict_even_when_threshold_met(tmp_path: Path) -> None:
    payload = {
        "run_type": "collector_bootstrap",
        "extractor_version": "x",
        "llm_model": None,
        "records": [
            _record(
                key="obs-conflict",
                pollster="한국갤럽",
                sponsor="서울신문",
                survey_end_date="2026-02-20",
                sample_size=1000,
                method="전화면접조사",
                response_rate=12.3,
                margin_of_error=3.1,
                raw_text="의뢰기관 서울신문 조사기관 한국갤럽 표본수 1,000명 전화면접조사 응답률 22.0% 오차범위 ±3.1%p 95% 신뢰수준",
            )
        ],
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = generate_collector_article_legal_completeness_v1_batch50(
        source_path=str(source),
        sample_size=1,
        threshold=0.8,
        eval_sample_size=1,
    )

    obs = out["batch"]["records"][0]["observation"]
    assert "response_rate" in obs["legal_conflict_fields"]
    assert out["report"]["risk_signals"]["issue_row_count"] == 1
    assert len(out["review_queue_candidates"]) == 1


def test_legal_required_fields_reports_precision_recall_on_30_sample(tmp_path: Path) -> None:
    records = [
        _record(
            key=f"obs-{idx}",
            pollster="한국갤럽",
            sponsor="서울신문",
            survey_end_date="2026-02-20",
            sample_size=1000,
            method="전화면접조사",
            response_rate=12.3,
            margin_of_error=3.1,
            raw_text="의뢰기관 서울신문 조사기관 한국갤럽 표본수 1,000명 전화면접조사 응답률 12.3% 오차범위 ±3.1%p 95% 신뢰수준",
        )
        for idx in range(35)
    ]
    payload = {
        "run_type": "collector_bootstrap",
        "extractor_version": "x",
        "llm_model": None,
        "records": records,
    }
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = generate_collector_article_legal_completeness_v1_batch50(
        source_path=str(source),
        sample_size=35,
        threshold=0.9,
        eval_sample_size=30,
    )

    pr = out["report"]["precision_recall"]
    assert pr["sample_size"] == 30
    assert out["report"]["acceptance_checks"]["eval_sample_size_eq_30"] is True
    assert pr["micro_precision"] == 1.0
    assert pr["micro_recall"] == 1.0
