from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.qa.run_candidate_token_backfill as script


def test_classify_backfill_reason_noise_token() -> None:
    row = {
        "option_name": "대비",
        "candidate_id": "cand:대비",
        "candidate_verify_source": "manual",
        "candidate_verify_confidence": 1.0,
        "candidate_verify_matched_key": "대비",
        "party_name": None,
    }
    assert script.classify_backfill_reason(row) == "noise_token"


def test_classify_backfill_reason_low_quality_manual_candidate() -> None:
    row = {
        "option_name": "후보님",
        "candidate_id": "cand:후보님",
        "candidate_verify_source": "manual",
        "candidate_verify_confidence": 1.0,
        "candidate_verify_matched_key": "후보님",
        "party_name": None,
    }
    assert script.classify_backfill_reason(row) == "low_quality_manual_candidate"


def test_classify_backfill_reason_keeps_valid_row() -> None:
    row = {
        "option_name": "정원오",
        "candidate_id": "cand-jwo",
        "candidate_verify_source": "data_go",
        "candidate_verify_confidence": 0.99,
        "candidate_verify_matched_key": "data_go:cand-jwo",
        "party_name": "더불어민주당",
    }
    assert script.classify_backfill_reason(row) is None


def test_run_backfill_dry_run_generates_report(monkeypatch, tmp_path: Path) -> None:
    rows = [
        {
            "id": 10,
            "observation_id": 100,
            "option_name": "대비",
            "candidate_id": "cand:대비",
            "party_name": None,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "candidate_verify_matched_key": "대비",
            "matchup_id": "20260603|광역자치단체장|11-000",
            "poll_fingerprint": "fp",
            "survey_end_date": "2026-02-20",
        }
    ]

    class _Conn:
        committed = False

        def commit(self) -> None:
            self.committed = True

    class _ConnCtx:
        def __enter__(self):
            return _Conn()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(script, "get_connection", lambda: _ConnCtx())
    monkeypatch.setattr(
        script,
        "fetch_candidate_rows",
        lambda conn, matchup_id, poll_fingerprint, limit: rows,
    )

    called = {"apply": False}

    def _apply(conn, target_ids, chunk_size):  # noqa: ARG001
        called["apply"] = True
        return {"updated_count": 0, "updated_ids": []}

    monkeypatch.setattr(script, "apply_backfill_targets", _apply)

    args = SimpleNamespace(
        mode="dry-run",
        matchup_id=None,
        poll_fingerprint=None,
        limit=1000,
        chunk_size=100,
        sample_limit=10,
        idempotency_check=True,
        output_dir=str(tmp_path / "out"),
        report=str(tmp_path / "report.json"),
    )

    report = script.run_backfill(args)

    assert report["mode"] == "dry-run"
    assert report["target_count"] == 1
    assert report["reason_counts"]["noise_token"] == 1
    assert called["apply"] is False
    assert Path(report["artifacts"]["targets"]).exists()
    persisted = json.loads(Path(args.report).read_text(encoding="utf-8"))
    assert persisted["target_count"] == 1


def test_run_backfill_apply_runs_idempotency_check(monkeypatch, tmp_path: Path) -> None:
    rows = [
        {
            "id": 21,
            "observation_id": 201,
            "option_name": "대비",
            "candidate_id": "cand:대비",
            "party_name": None,
            "candidate_verify_source": "manual",
            "candidate_verify_confidence": 1.0,
            "candidate_verify_matched_key": "대비",
            "matchup_id": "20260603|광역자치단체장|11-000",
            "poll_fingerprint": "fp2",
            "survey_end_date": "2026-02-21",
        }
    ]

    class _Conn:
        committed = False

        def commit(self) -> None:
            self.committed = True

    conn = _Conn()

    class _ConnCtx:
        def __enter__(self):
            return conn

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(script, "get_connection", lambda: _ConnCtx())
    monkeypatch.setattr(
        script,
        "fetch_candidate_rows",
        lambda conn, matchup_id, poll_fingerprint, limit: rows,
    )
    monkeypatch.setattr(
        script,
        "apply_backfill_targets",
        lambda conn, target_ids, chunk_size: {"updated_count": len(target_ids), "updated_ids": list(target_ids)},
    )
    monkeypatch.setattr(script, "verify_updated_rows_not_verified", lambda conn, updated_ids: 0)

    args = SimpleNamespace(
        mode="apply",
        matchup_id=None,
        poll_fingerprint=None,
        limit=1000,
        chunk_size=100,
        sample_limit=5,
        idempotency_check=True,
        output_dir=str(tmp_path / "out"),
        report=str(tmp_path / "report.json"),
    )

    report = script.run_backfill(args)

    assert report["mode"] == "apply"
    assert report["apply_result"]["updated_count"] == 1
    assert report["idempotency"]["checked"] is True
    assert report["idempotency"]["ok"] is True
    assert conn.committed is True
