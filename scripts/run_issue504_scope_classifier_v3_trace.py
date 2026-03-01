#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.ingest_service import (
    _apply_article_scope_hint_fallback,
    _apply_scope_region_conflict_resolution,
    _apply_survey_name_matchup_correction,
    _resolve_observation_scope,
    _sync_region_payload_from_observation,
)

DEFAULT_INPUT = Path("data/collector_live_news_v1_payload.json")
DEFAULT_TRACE_OUTPUT = Path("data/issue504_scope_classifier_v3_trace_samples.json")
DEFAULT_REPORT_OUTPUT = Path("data/issue504_scope_classifier_v3_report.json")
DEFAULT_TRACE_LIMIT = 20

REPRESENTATIVE_CASES: list[dict[str, Any]] = [
    {
        "case_id": "metro-busan-mayor",
        "article": {"title": "부산시장 양자대결", "raw_text": "부산시장 선거 관련 조사"},
        "observation": {
            "observation_key": "probe-26-000",
            "survey_name": "부산시장 지지도",
            "region_code": "26-710",
            "office_type": "기초자치단체장",
            "matchup_id": "2026_local|기초자치단체장|26-710",
            "audience_scope": None,
            "audience_region_code": None,
            "sampling_population_text": "부산 기장군 거주 만 18세 이상",
        },
        "expected_region_code": "26-000",
        "expected_office_type": "광역자치단체장",
    },
    {
        "case_id": "metro-gyeongnam-governor",
        "article": {"title": "경남지사 적합도", "raw_text": "경남지사 후보 조사"},
        "observation": {
            "observation_key": "probe-48-000",
            "survey_name": "경남지사 적합도",
            "region_code": "48-110",
            "office_type": "기초자치단체장",
            "matchup_id": "2026_local|기초자치단체장|48-110",
            "audience_scope": None,
            "audience_region_code": None,
            "sampling_population_text": "경상남도 거주 만 18세 이상",
        },
        "expected_region_code": "48-000",
        "expected_office_type": "광역자치단체장",
    },
    {
        "case_id": "metro-incheon-mayor",
        "article": {"title": "인천시장 지지도", "raw_text": "인천시장 선거 조사"},
        "observation": {
            "observation_key": "probe-28-000",
            "survey_name": "인천시장 후보 적합도",
            "region_code": "28-450",
            "office_type": "기초자치단체장",
            "matchup_id": "2026_local|기초자치단체장|28-450",
            "audience_scope": None,
            "audience_region_code": None,
            "sampling_population_text": "인천 연수구 거주 만 18세 이상",
        },
        "expected_region_code": "28-000",
        "expected_office_type": "광역자치단체장",
    },
    {
        "case_id": "local-yeonsu-gu",
        "article": {"title": "연수구청장 적합도", "raw_text": "연수구청장 조사"},
        "observation": {
            "observation_key": "probe-28-450",
            "survey_name": "연수구청장 적합도",
            "region_code": "28-000",
            "office_type": "광역자치단체장",
            "matchup_id": "2026_local|광역자치단체장|28-000",
            "audience_scope": None,
            "audience_region_code": None,
            "sampling_population_text": "인천 연수구 거주 만 18세 이상",
        },
        "expected_region_code": "28-450",
        "expected_office_type": "기초자치단체장",
    },
    {
        "case_id": "local-gijang-gun",
        "article": {"title": "기장군수 적합도", "raw_text": "기장군수 조사"},
        "observation": {
            "observation_key": "probe-26-710",
            "survey_name": "기장군수 적합도",
            "region_code": "26-000",
            "office_type": "광역자치단체장",
            "matchup_id": "2026_local|광역자치단체장|26-000",
            "audience_scope": None,
            "audience_region_code": None,
            "sampling_population_text": "부산 기장군 거주 만 18세 이상",
        },
        "expected_region_code": "26-710",
        "expected_office_type": "기초자치단체장",
    },
]


def _snapshot_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "region_code": observation.get("region_code"),
        "office_type": observation.get("office_type"),
        "matchup_id": observation.get("matchup_id"),
        "audience_scope": observation.get("audience_scope"),
        "audience_region_code": observation.get("audience_region_code"),
        "sampling_population_text": observation.get("sampling_population_text"),
    }


def _decision_source(
    *,
    question_signal_applied: bool,
    scope_resolution: Any,
    fallback_applied: bool,
) -> str:
    if question_signal_applied:
        return "question_text_or_official_code"
    if scope_resolution.inferred_scope or scope_resolution.inferred_region_code:
        return "sampling_population"
    if fallback_applied:
        return "article_title_body_hint"
    return "observation_default"


def _run_scope_classifier_step(
    *,
    article: dict[str, Any],
    observation: dict[str, Any],
    region: dict[str, Any] | None,
) -> dict[str, Any]:
    observation_payload = dict(observation)
    region_payload = dict(region) if region is not None else None
    before = _snapshot_observation(observation_payload)

    question_signal_applied = _apply_survey_name_matchup_correction(
        observation_payload=observation_payload,
        article_title=None,
    )
    scope_resolution = _resolve_observation_scope(
        observation_payload,
        prefer_declared_scope=question_signal_applied,
    )
    observation_payload["audience_scope"] = scope_resolution.scope
    observation_payload["audience_region_code"] = scope_resolution.audience_region_code
    conflict_resolution_applied = _apply_scope_region_conflict_resolution(
        observation_payload=observation_payload,
        inferred_region_code=scope_resolution.inferred_region_code,
    )

    fallback_applied = False
    fallback_keyword = None
    if not question_signal_applied and scope_resolution.inferred_region_code is None:
        fallback_applied, fallback_keyword = _apply_article_scope_hint_fallback(
            observation_payload=observation_payload,
            region_payload=region_payload,
            article_title=article.get("title"),
            article_raw_text=article.get("raw_text"),
        )

    synced_region_payload = _sync_region_payload_from_observation(
        region_payload=region_payload,
        observation_payload=observation_payload,
    )
    after = _snapshot_observation(observation_payload)
    return {
        "before": before,
        "after": after,
        "question_signal_applied": question_signal_applied,
        "scope_resolution": {
            "inferred_scope": scope_resolution.inferred_scope,
            "inferred_region_code": scope_resolution.inferred_region_code,
            "confidence": scope_resolution.confidence,
            "hard_fail_reason": scope_resolution.hard_fail_reason,
            "low_confidence_reason": scope_resolution.low_confidence_reason,
        },
        "conflict_resolution_applied": conflict_resolution_applied,
        "title_body_fallback_applied": fallback_applied,
        "title_body_keyword": fallback_keyword,
        "decision_source": _decision_source(
            question_signal_applied=question_signal_applied,
            scope_resolution=scope_resolution,
            fallback_applied=fallback_applied,
        ),
        "region_after_sync": synced_region_payload,
    }


def _load_records(input_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        return []
    return [row for row in records if isinstance(row, dict)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate scope-classifier-v3 trace/report for issue #504")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--trace-output", default=str(DEFAULT_TRACE_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--trace-limit", type=int, default=DEFAULT_TRACE_LIMIT)
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    trace_output = Path(args.trace_output)
    report_output = Path(args.report_output)
    trace_limit = max(1, int(args.trace_limit))

    records = _load_records(input_path)
    traces: list[dict[str, Any]] = []
    for record in records:
        article = record.get("article") or {}
        observation = record.get("observation") or {}
        if not isinstance(article, dict) or not isinstance(observation, dict):
            continue
        region = record.get("region")
        region_payload = region if isinstance(region, dict) else None
        trace = _run_scope_classifier_step(article=article, observation=observation, region=region_payload)
        trace["observation_key"] = observation.get("observation_key")
        traces.append(trace)
        if len(traces) >= trace_limit:
            break

    representative_results: list[dict[str, Any]] = []
    for case in REPRESENTATIVE_CASES:
        result = _run_scope_classifier_step(
            article=case["article"],
            observation=case["observation"],
            region=None,
        )
        after = result["after"]
        expected_region_code = case["expected_region_code"]
        expected_office_type = case["expected_office_type"]
        representative_results.append(
            {
                "case_id": case["case_id"],
                "expected_region_code": expected_region_code,
                "expected_office_type": expected_office_type,
                "actual_region_code": after.get("region_code"),
                "actual_office_type": after.get("office_type"),
                "pass": after.get("region_code") == expected_region_code and after.get("office_type") == expected_office_type,
                "decision_source": result["decision_source"],
                "scope_resolution": result["scope_resolution"],
            }
        )

    report = {
        "issue": 504,
        "algorithm_version": "scope_classifier_v3",
        "input_path": str(input_path),
        "trace_sample_count": len(traces),
        "trace_limit": trace_limit,
        "representative_case_count": len(representative_results),
        "representative_pass_count": sum(1 for row in representative_results if row["pass"]),
        "acceptance_checks": {
            "trace_sample_count_ge_20": len(traces) >= 20,
            "representative_cases_all_pass": all(row["pass"] for row in representative_results),
            "metro_examples_fixed": all(
                row["pass"] for row in representative_results if row["case_id"] in {"metro-busan-mayor", "metro-gyeongnam-governor", "metro-incheon-mayor"}
            ),
            "local_leak_zero_for_28_450_26_710": all(
                row["pass"] for row in representative_results if row["case_id"] in {"local-yeonsu-gu", "local-gijang-gun"}
            ),
        },
        "representative_results": representative_results,
    }

    trace_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    trace_output.write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"written: {trace_output}")
    print(f"written: {report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
