#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.ingest_service import _resolve_observation_scope

OUT_EVAL = Path("data/issue387_scope_inference_v3_eval.json")
OUT_SAMPLES = Path("data/issue387_scope_inference_v3_eval_samples.json")


def _case(
    case_id: str,
    *,
    sampling_population_text: str,
    region_code: str,
    expected_scope: str,
    expected_region_code: str | None,
    audience_scope: str | None = None,
    audience_region_code: str | None = None,
    expect_hard_fail: bool = False,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "sampling_population_text": sampling_population_text,
        "region_code": region_code,
        "audience_scope": audience_scope,
        "audience_region_code": audience_region_code,
        "expected_scope": expected_scope,
        "expected_region_code": expected_region_code,
        "expect_hard_fail": expect_hard_fail,
    }


CASES: list[dict[str, Any]] = [
    _case("nat-01", sampling_population_text="전국 만 18세 이상 남녀", region_code="11-000", expected_scope="national", expected_region_code=None),
    _case("nat-02", sampling_population_text="대한민국 거주 만 18세 이상", region_code="26-000", expected_scope="national", expected_region_code=None),
    _case("nat-03", sampling_population_text="전국 거주 성인 남녀", region_code="41-000", expected_scope="national", expected_region_code=None),
    _case("nat-04", sampling_population_text="전국민 대상 조사", region_code="42-000", expected_scope="national", expected_region_code=None),
    _case("nat-05", sampling_population_text="전국 만 18세 이상 유권자", region_code="47-000", expected_scope="national", expected_region_code=None),
    _case("nat-06", sampling_population_text="전국 18세 이상 휴대전화 가상번호", region_code="29-000", expected_scope="national", expected_region_code=None),
    _case("nat-07", sampling_population_text="전국 만 18세 이상 남녀 1000명", region_code="11-000", expected_scope="national", expected_region_code=None),
    _case("nat-08", sampling_population_text="전국 거주자 18세 이상", region_code="30-000", expected_scope="national", expected_region_code=None),
    _case("nat-09", sampling_population_text="전국 성인 남녀 대상", region_code="31-000", expected_scope="national", expected_region_code=None),
    _case("nat-10", sampling_population_text="전국 만18세 이상 남녀", region_code="36-000", expected_scope="national", expected_region_code=None),
    _case("nat-11", sampling_population_text="전국민 만 18세 이상", region_code="45-000", expected_scope="national", expected_region_code=None),
    _case("nat-12", sampling_population_text="전국 단위 표본", region_code="48-000", expected_scope="national", expected_region_code=None),
    _case("reg-01", sampling_population_text="서울시 거주 만 18세 이상 남녀", region_code="11-000", expected_scope="regional", expected_region_code="11-000"),
    _case("reg-02", sampling_population_text="부산광역시 거주 만 18세 이상", region_code="26-000", expected_scope="regional", expected_region_code="26-000"),
    _case("reg-03", sampling_population_text="대구시 거주 만 18세 이상", region_code="27-000", expected_scope="regional", expected_region_code="27-000"),
    _case("reg-04", sampling_population_text="인천광역시 거주 만 18세 이상", region_code="28-000", expected_scope="regional", expected_region_code="28-000"),
    _case("reg-05", sampling_population_text="광주시 거주 만 18세 이상", region_code="29-000", expected_scope="regional", expected_region_code="29-000"),
    _case("reg-06", sampling_population_text="대전광역시 거주 성인 남녀", region_code="30-000", expected_scope="regional", expected_region_code="30-000"),
    _case("reg-07", sampling_population_text="울산광역시 거주 만 18세 이상", region_code="31-000", expected_scope="regional", expected_region_code="31-000"),
    _case("reg-08", sampling_population_text="경기도 거주 만 18세 이상", region_code="41-000", expected_scope="regional", expected_region_code="41-000"),
    _case("reg-09", sampling_population_text="강원특별자치도 거주 만 18세 이상", region_code="42-000", expected_scope="regional", expected_region_code="42-000"),
    _case("reg-10", sampling_population_text="전북특별자치도 거주 만 18세 이상", region_code="45-000", expected_scope="regional", expected_region_code="45-000"),
    _case("reg-11", sampling_population_text="경상남도 거주 만 18세 이상", region_code="48-000", expected_scope="regional", expected_region_code="48-000"),
    _case("reg-12", sampling_population_text="제주특별자치도 거주 만 18세 이상", region_code="50-000", expected_scope="regional", expected_region_code="50-000"),
    _case("loc-01", sampling_population_text="서울 강남구 거주 만 18세 이상", region_code="11-680", expected_scope="local", expected_region_code="11-680"),
    _case("loc-02", sampling_population_text="서울 송파구 거주 만 18세 이상", region_code="11-710", expected_scope="local", expected_region_code="11-710"),
    _case("loc-03", sampling_population_text="서울 서초구 거주 만 18세 이상", region_code="11-650", expected_scope="local", expected_region_code="11-650"),
    _case("loc-04", sampling_population_text="부산 기장군 거주 만 18세 이상", region_code="26-710", expected_scope="local", expected_region_code="26-710"),
    _case("loc-05", sampling_population_text="부산 해운대구 거주 만 18세 이상", region_code="26-350", expected_scope="local", expected_region_code="26-350"),
    _case("loc-06", sampling_population_text="인천 연수구 거주 만 18세 이상", region_code="28-450", expected_scope="local", expected_region_code="28-450"),
    _case("loc-07", sampling_population_text="강원 춘천시 거주 만 18세 이상", region_code="42-110", expected_scope="local", expected_region_code="42-110"),
    _case("loc-08", sampling_population_text="충북 청주시 거주 만 18세 이상", region_code="43-110", expected_scope="local", expected_region_code="43-110"),
    _case("loc-09", sampling_population_text="제주 제주시 거주 만 18세 이상", region_code="50-110", expected_scope="local", expected_region_code="50-110"),
    _case("loc-10", sampling_population_text="제주 서귀포시 거주 만 18세 이상", region_code="50-130", expected_scope="local", expected_region_code="50-130"),
    _case(
        "conf-01",
        sampling_population_text="서울시 거주 만 18세 이상",
        region_code="11-000",
        audience_scope="national",
        expected_scope="national",
        expected_region_code=None,
        expect_hard_fail=True,
    ),
    _case(
        "conf-02",
        sampling_population_text="부산시 거주 만 18세 이상",
        region_code="26-000",
        audience_scope="national",
        expected_scope="national",
        expected_region_code=None,
        expect_hard_fail=True,
    ),
    _case(
        "conf-03",
        sampling_population_text="서울시 거주 만 18세 이상",
        region_code="11-000",
        audience_scope="regional",
        audience_region_code="26-000",
        expected_scope="regional",
        expected_region_code="26-000",
        expect_hard_fail=True,
    ),
    _case(
        "conf-04",
        sampling_population_text="강남구 거주 만 18세 이상",
        region_code="11-680",
        audience_scope="regional",
        audience_region_code="11-000",
        expected_scope="regional",
        expected_region_code="11-000",
        expect_hard_fail=True,
    ),
]


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    observation = {
        "region_code": case["region_code"],
        "audience_scope": case.get("audience_scope"),
        "audience_region_code": case.get("audience_region_code"),
        "sampling_population_text": case.get("sampling_population_text"),
    }
    resolved = _resolve_observation_scope(observation)

    predicted_hard_fail = bool(resolved.hard_fail_reason)
    expected_hard_fail = bool(case.get("expect_hard_fail"))
    scope_match = resolved.scope == case.get("expected_scope")
    region_match = resolved.audience_region_code == case.get("expected_region_code")

    return {
        "case_id": case["case_id"],
        "expected_scope": case.get("expected_scope"),
        "expected_region_code": case.get("expected_region_code"),
        "expect_hard_fail": expected_hard_fail,
        "predicted_scope": resolved.scope,
        "predicted_region_code": resolved.audience_region_code,
        "predicted_hard_fail": predicted_hard_fail,
        "inferred_scope": resolved.inferred_scope,
        "inferred_region_code": resolved.inferred_region_code,
        "confidence": resolved.confidence,
        "hard_fail_reason": resolved.hard_fail_reason,
        "low_confidence_reason": resolved.low_confidence_reason,
        "scope_match": scope_match,
        "region_match": region_match,
        "hard_fail_match": predicted_hard_fail == expected_hard_fail,
        "pass": (
            (predicted_hard_fail == expected_hard_fail)
            and (expected_hard_fail or (scope_match and region_match))
        ),
    }


def main() -> int:
    samples = [_evaluate_case(case) for case in CASES]

    conflict_cases = [row for row in samples if row["expect_hard_fail"]]
    eval_cases = [row for row in samples if not row["expect_hard_fail"]]

    total = len(samples)
    eval_total = len(eval_cases)
    conflict_total = len(conflict_cases)

    scope_correct = sum(1 for row in eval_cases if row["scope_match"])
    scope_region_correct = sum(1 for row in eval_cases if row["scope_match"] and row["region_match"])
    hard_fail_correct = sum(1 for row in conflict_cases if row["hard_fail_match"])

    report = {
        "issue": 387,
        "algorithm_version": "scope_inference_v3",
        "sample_count": total,
        "eval_sample_count": eval_total,
        "conflict_sample_count": conflict_total,
        "scope_precision": round(scope_correct / eval_total, 4) if eval_total else None,
        "scope_region_precision": round(scope_region_correct / eval_total, 4) if eval_total else None,
        "hard_fail_detection_recall": round(hard_fail_correct / conflict_total, 4) if conflict_total else None,
        "acceptance_checks": {
            "sample_count_ge_30": total >= 30,
            "scope_precision_ge_0_9": (scope_correct / eval_total) >= 0.9 if eval_total else False,
            "scope_region_precision_ge_0_9": (scope_region_correct / eval_total) >= 0.9 if eval_total else False,
            "hard_fail_detection_recall_ge_0_9": (hard_fail_correct / conflict_total) >= 0.9 if conflict_total else False,
        },
    }

    OUT_EVAL.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SAMPLES.write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"written: {OUT_EVAL}")
    print(f"written: {OUT_SAMPLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
