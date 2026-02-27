from __future__ import annotations

import json

import scripts.generate_collector_scope_hardguard_cutoff_eval as scope_eval


def test_scope_hardguard_cutoff_eval_outputs_expected_metrics(tmp_path) -> None:
    scope_eval.OUT_EVAL = tmp_path / "issue465_eval.json"
    scope_eval.OUT_SAMPLES = tmp_path / "issue465_eval_samples.json"

    code = scope_eval.main()

    assert code == 0
    report = json.loads(scope_eval.OUT_EVAL.read_text(encoding="utf-8"))
    samples = json.loads(scope_eval.OUT_SAMPLES.read_text(encoding="utf-8"))

    assert report["sample_count"] >= 30
    assert report["keyword_record_count"] > 0
    assert report["acceptance_checks"]["sample_count_ge_30"] is True
    assert report["acceptance_checks"]["hardguard_basic_scope_violation_zero"] is True
    assert report["acceptance_checks"]["old_article_ingest_zero"] is True
    assert report["acceptance_checks"]["old_article_cutoff_review_logged"] is True
    assert report["acceptance_checks"]["scenario_parse_incomplete_review_logged"] is True
    assert len(samples["old_article_cutoff_reviews"]) >= 1
    assert len(samples["scenario_parse_incomplete_reviews"]) >= 1
