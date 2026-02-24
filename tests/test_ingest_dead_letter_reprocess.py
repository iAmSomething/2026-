from __future__ import annotations

import json
import os
from pathlib import Path

from app.jobs.ingest_runner import AttemptLog, IngestRunnerResult
from scripts.qa.reprocess_ingest_dead_letter import reprocess_dead_letter_record, resolve_dead_letter_path
from scripts.qa.run_ingest_with_retry import write_dead_letter_record


def _failed_result() -> IngestRunnerResult:
    return IngestRunnerResult(
        success=False,
        attempts=[
            AttemptLog(
                attempt=1,
                http_status=500,
                job_status=None,
                failure_class="http_5xx",
                failure_type="http_5xx",
                retryable=True,
                request_timeout_seconds=30.0,
                error=None,
                detail="server error",
            )
        ],
        run_ids=[],
        finished_at="2026-02-24T00:00:00+00:00",
        failure_class="http_5xx",
        failure_type="http_5xx",
        failure_reason="http_5xx: http_status=500",
    )


def _success_result() -> IngestRunnerResult:
    return IngestRunnerResult(
        success=True,
        attempts=[
            AttemptLog(
                attempt=1,
                http_status=200,
                job_status="success",
                failure_class=None,
                failure_type=None,
                retryable=False,
                request_timeout_seconds=30.0,
                error=None,
                detail=None,
            )
        ],
        run_ids=[123],
        finished_at="2026-02-24T00:00:00+00:00",
        failure_class=None,
        failure_type=None,
        failure_reason=None,
    )


def test_write_dead_letter_record(tmp_path: Path) -> None:
    payload = {"run_type": "collector_live_coverage_v2", "records": []}
    out = write_dead_letter_record(
        dead_letter_dir=tmp_path,
        source_input_path="data/collector_live_payload.json",
        payload=payload,
        result=_failed_result(),
        report_path="data/ingest_schedule_report.json",
    )

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert out.exists()
    assert out.name.startswith("ingest_dead_letter_")
    assert saved["failure_type"] == "http_5xx"
    assert saved["status"] == "pending"
    assert saved["payload"]["run_type"] == "collector_live_coverage_v2"
    assert len(saved["payload_digest"]) == 64


def test_reprocess_dead_letter_record_updates_status(tmp_path: Path) -> None:
    record_path = tmp_path / "ingest_dead_letter_test.json"
    record_path.write_text(
        json.dumps(
            {
                "created_at": "2026-02-24T00:00:00+00:00",
                "payload": {"run_type": "collector_live_coverage_v2", "records": []},
                "status": "pending",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "reprocess_report.json"

    called = {"count": 0}

    def runner_fn(**kwargs):
        called["count"] += 1
        assert kwargs["api_base_url"] == "http://127.0.0.1:8100"
        assert kwargs["token"] == "token"
        return _success_result()

    result = reprocess_dead_letter_record(
        dead_letter_path=record_path,
        api_base_url="http://127.0.0.1:8100",
        token="token",
        report_path=str(report_path),
        max_retries=1,
        backoff_seconds=1.0,
        timeout=30.0,
        timeout_scale_on_timeout=1.5,
        timeout_max=300.0,
        runner_fn=runner_fn,
    )

    assert called["count"] == 1
    assert result.success is True
    assert report_path.exists()

    updated = json.loads(record_path.read_text(encoding="utf-8"))
    assert updated["status"] == "resolved"
    assert updated["reprocess_attempts"]
    assert updated["reprocess_attempts"][0]["success"] is True


def test_resolve_dead_letter_path_latest(tmp_path: Path) -> None:
    older = tmp_path / "ingest_dead_letter_older.json"
    newer = tmp_path / "ingest_dead_letter_newer.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    resolved = resolve_dead_letter_path(dead_letter=None, dead_letter_dir=str(tmp_path), latest=True)
    assert resolved == newer
