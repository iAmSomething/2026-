from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.qa.reprocess_single_matchup as script


def _source_row() -> dict:
    return {
        "observation_id": 11,
        "article_id": 21,
        "observation_key": "obs-11",
        "survey_name": "테스트 조사",
        "pollster": "테스트리서치",
        "survey_start_date": "2026-02-20",
        "survey_end_date": "2026-02-21",
        "confidence_level": 95.0,
        "sample_size": 1000,
        "response_rate": 14.2,
        "margin_of_error": 3.1,
        "sponsor": "테스트",
        "method": "전화면접",
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "matchup_id": "20260603|광역자치단체장|11-000",
        "audience_scope": "regional",
        "audience_region_code": "11-000",
        "sampling_population_text": "만18세 이상",
        "legal_completeness_score": 1.0,
        "legal_filled_count": 5,
        "legal_required_count": 5,
        "date_resolution": "exact",
        "date_inference_mode": "none",
        "date_inference_confidence": 1.0,
        "poll_fingerprint": "f" * 64,
        "source_channel": "article",
        "source_channels": ["article"],
        "official_release_at": None,
        "verified": True,
        "source_grade": "A",
        "article_url": "https://example.com/a",
        "article_title": "제목",
        "article_publisher": "언론사",
        "article_published_at": "2026-02-21T00:00:00+00:00",
        "article_raw_text": "본문",
        "article_raw_hash": "h" * 64,
    }


def _option_rows() -> list[dict]:
    return [
        {
            "option_type": "candidate_matchup",
            "option_name": "후보A",
            "candidate_id": "cand-a",
            "party_name": "정당A",
            "scenario_key": "h2h-a-b",
            "scenario_type": "head_to_head",
            "scenario_title": "A vs B",
            "value_raw": "53~55%",
            "value_min": 53.0,
            "value_max": 55.0,
            "value_mid": 54.0,
            "is_missing": False,
            "party_inferred": False,
            "party_inference_source": None,
            "party_inference_confidence": None,
            "candidate_verified": True,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "needs_manual_review": False,
        },
        {
            "option_type": "candidate_matchup",
            "option_name": "후보B",
            "candidate_id": "cand-b",
            "party_name": "정당B",
            "scenario_key": "h2h-a-b",
            "scenario_type": "head_to_head",
            "scenario_title": "A vs B",
            "value_raw": "45%",
            "value_min": 45.0,
            "value_max": 45.0,
            "value_mid": 45.0,
            "is_missing": False,
            "party_inferred": False,
            "party_inference_source": None,
            "party_inference_confidence": None,
            "candidate_verified": True,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "needs_manual_review": False,
        },
    ]


def _snapshot() -> dict:
    return {
        "observation_count": 1,
        "distinct_observation_keys": 1,
        "distinct_poll_fingerprints": 1,
        "distinct_matchup_ids": 1,
        "option_count": 2,
        "observation_ids": [11],
    }


def test_build_observation_where_clause_requires_filter() -> None:
    try:
        script.build_observation_where_clause(matchup_id=None, poll_fingerprint=None)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_build_observation_where_clause_combines_filters() -> None:
    where_sql, params = script.build_observation_where_clause(
        matchup_id="m1",
        poll_fingerprint="fp1",
    )
    assert where_sql == "o.matchup_id = %s AND o.poll_fingerprint = %s"
    assert params == ("m1", "fp1")


def test_build_idempotency_evidence_detects_new_ids() -> None:
    evidence = script.build_idempotency_evidence(
        {"observation_ids": [1, 2], "option_count": 2},
        {"observation_ids": [1, 2, 3], "option_count": 3},
    )
    assert evidence["new_observation_ids"] == [3]
    assert evidence["count_delta"]["option_count"] == 1


def test_main_apply_generates_before_after_artifacts_and_idempotent_pass(
    monkeypatch,
    tmp_path: Path,
) -> None:
    args = SimpleNamespace(
        matchup_id="20260603|광역자치단체장|11-000",
        poll_fingerprint="f" * 64,
        mode="apply",
        idempotency_check=True,
        output_dir=str(tmp_path / "out"),
        tag="t",
        report=str(tmp_path / "report.json"),
    )
    monkeypatch.setattr(script, "parse_args", lambda: args)

    class _ConnCtx:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(script, "get_connection", lambda: _ConnCtx())
    monkeypatch.setattr(script, "fetch_target_observation", lambda conn, **kwargs: _source_row())
    monkeypatch.setattr(script, "fetch_poll_options", lambda conn, observation_id: _option_rows())
    monkeypatch.setattr(
        script,
        "fetch_region_row",
        lambda conn, region_code: {
            "region_code": region_code,
            "sido_name": "서울",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
    )

    class _Payload:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def model_dump(self, mode: str = "json") -> dict:
            return self._payload

    monkeypatch.setattr(script.IngestPayload, "model_validate", lambda payload: _Payload(payload))

    snapshots = [_snapshot(), _snapshot(), _snapshot()]
    monkeypatch.setattr(script, "collect_snapshot", lambda conn, matchup_id, poll_fingerprint: snapshots.pop(0))
    monkeypatch.setattr(
        script,
        "ingest_payload",
        lambda payload, repo: SimpleNamespace(
            run_id=1,
            processed_count=1,
            error_count=0,
            status="success",
        ),
    )
    monkeypatch.setattr(script, "PostgresRepository", lambda conn: object())

    exit_code = script.main()
    assert exit_code == 0

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    assert report["status"] == "success"
    assert report["mode"] == "apply"
    assert report["idempotent_ok"] is True
    assert report["idempotency_evidence"]["new_observation_ids"] == []
    assert report["delta_after_first_to_after_second"]["observation_count"] == 0
    assert Path(report["artifacts"]["before_snapshot"]).exists()
    assert Path(report["artifacts"]["after_snapshot"]).exists()
