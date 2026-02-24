from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_nesdc_live_v1_pack import build_nesdc_live_v1_pack


def _safe_collect_output(*, parse_success: int = 22) -> dict:
    return {
        "data": {
            "run_type": "collector_nesdc_safe_collect_v1",
            "records": [
                {
                    "ntt_id": "n1",
                    "pollster": "기관A",
                    "detail_url": "https://nesdc.test/n1",
                    "legal_meta": {
                        "survey_datetime": "2026-02-20",
                        "sample_size": "1,000명",
                        "margin_of_error": "95% 신뢰수준 ±3.1%p",
                    },
                },
                {
                    "ntt_id": "n2",
                    "pollster": "기관B",
                    "detail_url": "https://nesdc.test/n2",
                    "legal_meta": {
                        "survey_datetime": "2026-02-20",
                        "sample_size": 1000,
                        "margin_of_error": "±3.1%p",
                    },
                },
                {
                    "ntt_id": "n3",
                    "pollster": "기관C",
                    "detail_url": "https://nesdc.test/n3",
                    "legal_meta": {
                        "survey_datetime": "2026-02-21",
                        "sample_size": 800,
                        "margin_of_error": "±3.5%p",
                    },
                },
            ],
        },
        "report": {
            "counts": {
                "collected_success_count": parse_success,
                "eligible_48h_total": 30,
                "hard_fallback_count": 1,
            },
            "acceptance_checks": {
                "safe_window_applied_all": True,
            },
        },
        "review_queue_candidates": [
            {
                "entity_type": "poll_observation",
                "entity_id": "base-rq-1",
                "issue_type": "extract_error",
            }
        ],
    }


def _write_article_payload(path: Path) -> None:
    payload = {
        "records": [
            {
                "article": {"url": "https://news.test/a"},
                "observation": {
                    "observation_key": "obs-a",
                    "matchup_id": "M-SEOUL",
                    "pollster": "기관A",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 1000,
                    "margin_of_error": "±3.1%p",
                },
            },
            {
                "article": {"url": "https://news.test/b"},
                "observation": {
                    "observation_key": "obs-b",
                    "matchup_id": "M-BUSAN",
                    "pollster": "기관B",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 900,
                    "margin_of_error": "±3.0%p",
                },
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_nesdc_live_pack_merge_policy_and_review_queue(tmp_path: Path) -> None:
    article_path = tmp_path / "article_payload.json"
    _write_article_payload(article_path)

    out = build_nesdc_live_v1_pack(
        article_payload_path=str(article_path),
        safe_collect_output=_safe_collect_output(parse_success=22),
    )

    decisions = out["merge_evidence"]["decision_counts"]
    assert decisions.get("merge_exact") == 1
    assert decisions.get("conflict_review") == 1
    assert decisions.get("insert_new") == 1

    review_queue = out["review_queue_candidates"]
    assert len(review_queue) == 2
    assert any(x.get("error_code") == "ARTICLE_NESDC_CONFLICT" for x in review_queue)

    checks = out["report"]["acceptance_checks"]
    assert checks["parse_success_ge_20"] is True
    assert checks["safe_window_policy_applied"] is True
    assert checks["adapter_failure_review_queue_synced"] is True
    assert checks["article_merge_policy_evidence_present"] is True
    assert out["report"]["risk_signals"]["adapter_failure_present"] is True
    assert out["report"]["risk_signals"]["merge_conflict_present"] is True


def test_nesdc_live_pack_parse_success_threshold(tmp_path: Path) -> None:
    article_path = tmp_path / "article_payload.json"
    _write_article_payload(article_path)

    out = build_nesdc_live_v1_pack(
        article_payload_path=str(article_path),
        safe_collect_output=_safe_collect_output(parse_success=19),
    )

    assert out["report"]["acceptance_checks"]["parse_success_ge_20"] is False
    assert out["report"]["risk_signals"]["parse_success_below_floor"] is True


def test_nesdc_live_pack_best_match_not_first_candidate(tmp_path: Path) -> None:
    article_path = tmp_path / "article_payload.json"
    payload = {
        "records": [
            {
                "article": {"url": "https://news.test/wrong"},
                "observation": {
                    "observation_key": "obs-wrong",
                    "matchup_id": "M-SEOUL",
                    "pollster": "기관A",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 900,
                    "margin_of_error": "±3.0%p",
                },
            },
            {
                "article": {"url": "https://news.test/exact"},
                "observation": {
                    "observation_key": "obs-exact",
                    "matchup_id": "M-SEOUL",
                    "pollster": "기관A",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 1000,
                    "margin_of_error": "±3.1%p",
                },
            },
        ]
    }
    article_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = build_nesdc_live_v1_pack(
        article_payload_path=str(article_path),
        safe_collect_output={
            **_safe_collect_output(parse_success=22),
            "data": {
                "run_type": "collector_nesdc_safe_collect_v1",
                "records": [_safe_collect_output()["data"]["records"][0]],
            },
            "review_queue_candidates": [],
        },
    )

    decisions = out["merge_evidence"]["decision_samples"]
    assert decisions[0]["decision"] == "merge_exact"
    assert decisions[0]["article_observation_key"] == "obs-exact"
    assert decisions[0]["selection_basis"]["candidate_count"] == 2


def test_nesdc_live_pack_tie_candidates_route_conflict_review(tmp_path: Path) -> None:
    article_path = tmp_path / "article_payload.json"
    payload = {
        "records": [
            {
                "article": {"url": "https://news.test/one"},
                "observation": {
                    "observation_key": "obs-1",
                    "matchup_id": "M-SEOUL",
                    "pollster": "기관A",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 1000,
                    "margin_of_error": "±3.1%p",
                },
            },
            {
                "article": {"url": "https://news.test/two"},
                "observation": {
                    "observation_key": "obs-2",
                    "matchup_id": "M-SEOUL",
                    "pollster": "기관A",
                    "survey_end_date": "2026-02-20",
                    "sample_size": 1000,
                    "margin_of_error": "±3.1%p",
                },
            },
        ]
    }
    article_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    out = build_nesdc_live_v1_pack(
        article_payload_path=str(article_path),
        safe_collect_output={
            **_safe_collect_output(parse_success=22),
            "data": {
                "run_type": "collector_nesdc_safe_collect_v1",
                "records": [_safe_collect_output()["data"]["records"][0]],
            },
            "review_queue_candidates": [],
        },
    )

    assert out["merge_evidence"]["decision_counts"].get("conflict_review") == 1
    decision = out["merge_evidence"]["decision_samples"][0]
    assert decision["reason"] == "tie"
    assert decision["selection_basis"]["tie_with_next"] is True
    assert any(x.get("error_code") == "ARTICLE_NESDC_CONFLICT" for x in out["review_queue_candidates"])
