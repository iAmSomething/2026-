from __future__ import annotations

import json

import scripts.generate_collector_scope_inference_v3_eval as scope_eval


def test_scope_eval_case_count_meets_minimum() -> None:
    assert len(scope_eval.CASES) >= 30


def test_scope_eval_script_outputs_expected_metrics(tmp_path) -> None:
    scope_eval.OUT_EVAL = tmp_path / "scope_eval.json"
    scope_eval.OUT_SAMPLES = tmp_path / "scope_eval_samples.json"

    code = scope_eval.main()

    assert code == 0
    report = json.loads(scope_eval.OUT_EVAL.read_text(encoding="utf-8"))
    samples = json.loads(scope_eval.OUT_SAMPLES.read_text(encoding="utf-8"))

    assert report["sample_count"] >= 30
    assert report["acceptance_checks"]["sample_count_ge_30"] is True
    assert report["acceptance_checks"]["scope_precision_ge_0_9"] is True
    assert report["acceptance_checks"]["scope_region_precision_ge_0_9"] is True
    assert report["acceptance_checks"]["hard_fail_detection_recall_ge_0_9"] is True
    assert len(samples) == report["sample_count"]
    assert any(row["expect_hard_fail"] is True for row in samples)
