from __future__ import annotations

import json
from pathlib import Path

from app.jobs.ingest_runner import AttemptLog, IngestRunnerResult
from scripts.qa.run_ingest_with_retry import (
    execute_ingest_with_adaptive_chunks,
    is_effective_success,
    write_failure_classification_artifact,
    write_failure_comment_template,
)


def _result(*, success: bool, failure_class: str | None) -> IngestRunnerResult:
    return IngestRunnerResult(
        success=success,
        attempts=[
            AttemptLog(
                attempt=1,
                http_status=200,
                job_status="partial_success" if failure_class else "success",
                failure_class=failure_class,
                failure_type=failure_class,
                cause_code=failure_class,
                retryable=False,
                request_timeout_seconds=30.0,
            )
        ],
        run_ids=[1],
        finished_at="2026-02-24T00:00:00+00:00",
        failure_class=failure_class,
        failure_type=failure_class,
        cause_code=failure_class,
        failure_reason=None,
    )


def _result_with_records(
    *,
    success: bool,
    failure_class: str | None,
    cause_code: str | None = None,
    elapsed_seconds: float = 1.0,
) -> IngestRunnerResult:
    return IngestRunnerResult(
        success=success,
        attempts=[
            AttemptLog(
                attempt=1,
                http_status=200 if success else 503,
                job_status="success" if success else "failed",
                failure_class=failure_class,
                failure_type=failure_class,
                cause_code=cause_code,
                retryable=False,
                request_timeout_seconds=30.0,
                duration_seconds=elapsed_seconds,
                started_at="2026-02-24T00:00:00+00:00",
                finished_at="2026-02-24T00:00:01+00:00",
            )
        ],
        run_ids=[1] if success else [],
        started_at="2026-02-24T00:00:00+00:00",
        finished_at="2026-02-24T00:00:01+00:00",
        elapsed_seconds=elapsed_seconds,
        failure_class=failure_class,
        failure_type=failure_class,
        cause_code=cause_code,
        failure_reason=None,
    )


def test_effective_success_true_when_raw_success() -> None:
    result = _result(success=True, failure_class=None)
    assert is_effective_success(result, allow_partial_success=False) is True


def test_effective_success_true_when_partial_allowed() -> None:
    result = _result(success=False, failure_class="job_partial_success")
    assert is_effective_success(result, allow_partial_success=True) is True


def test_effective_success_false_when_partial_not_allowed() -> None:
    result = _result(success=False, failure_class="job_partial_success")
    assert is_effective_success(result, allow_partial_success=False) is False


def test_write_failure_classification_artifact(tmp_path: Path) -> None:
    result = _result(success=False, failure_class="timeout")
    out = write_failure_classification_artifact(
        path=tmp_path / "classification.json",
        source_input_path="data/collector_live_news_v1_payload.json",
        payload={"run_type": "collector_live_news_v1", "records": [1, 2, 3]},
        result=result,
        success=False,
        raw_success=False,
        dead_letter_path="data/dead_letter/file.json",
    )

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["schema_version"] == "collector_ingest_failure_classification.v1"
    assert saved["runner"]["failure_class"] == "timeout"
    assert saved["runner"]["cause_code"] == "timeout"
    assert saved["runner"]["attempt_count"] == 1
    assert saved["payload_record_count"] == 3
    assert saved["dead_letter_path"] == "data/dead_letter/file.json"
    assert saved["attempt_timeline"][0]["cause_code"] == "timeout"


def test_write_failure_comment_template(tmp_path: Path) -> None:
    result = _result(success=False, failure_class="db_auth_failed")
    out = write_failure_comment_template(
        path=tmp_path / "comment.md",
        report_path="data/ingest_schedule_report.json",
        classification_artifact_path="data/ingest_schedule_failure_classification.json",
        dead_letter_path="data/dead_letter/dead.json",
        result=result,
    )
    text = out.read_text(encoding="utf-8")
    assert "[DEVELOP][INGEST FAILURE TEMPLATE]" in text
    assert "classification_artifact" in text
    assert "next_status: status/in-progress" in text


def test_execute_ingest_with_adaptive_chunks_splits_timeout_chunk() -> None:
    def runner_fn(**kwargs):  # noqa: ANN003
        count = len(kwargs["payload"]["records"])
        if count > 20:
            return _result_with_records(
                success=False,
                failure_class="timeout",
                cause_code="timeout_request",
                elapsed_seconds=3.0,
            )
        return _result_with_records(success=True, failure_class=None, elapsed_seconds=1.2)

    payload = {"run_type": "collector_live_news_v1", "records": list(range(40))}
    result, effective_success, raw_success, chunking_summary, latency_profile = execute_ingest_with_adaptive_chunks(
        api_base="http://127.0.0.1:8100",
        token="token",
        payload=payload,
        max_retries=0,
        backoff_seconds=1.0,
        timeout=60.0,
        timeout_scale_on_timeout=1.5,
        timeout_max=180.0,
        heartbeat_interval_seconds=0.0,
        allow_partial_success=False,
        enable_timeout_chunk_downshift=True,
        chunk_target_records=0,
        chunk_min_records=10,
        chunk_downshift_factor=0.5,
        max_chunk_splits=4,
        max_total_chunks=10,
        runner_fn=runner_fn,
    )

    assert effective_success is True
    assert raw_success is True
    assert result.success is True
    assert result.failure_class is None
    assert chunking_summary["split_count"] == 1
    assert chunking_summary["completed_chunk_count"] == 3
    assert latency_profile["attempt_count"] == 3
    assert latency_profile["chunk_count"] == 3


def test_execute_ingest_with_adaptive_chunks_keeps_non_timeout_failure() -> None:
    def runner_fn(**kwargs):  # noqa: ANN003
        _ = kwargs
        return _result_with_records(
            success=False,
            failure_class="http_5xx",
            cause_code="http_503",
            elapsed_seconds=2.0,
        )

    payload = {"run_type": "collector_live_news_v1", "records": list(range(30))}
    result, effective_success, raw_success, chunking_summary, latency_profile = execute_ingest_with_adaptive_chunks(
        api_base="http://127.0.0.1:8100",
        token="token",
        payload=payload,
        max_retries=0,
        backoff_seconds=1.0,
        timeout=60.0,
        timeout_scale_on_timeout=1.5,
        timeout_max=180.0,
        heartbeat_interval_seconds=0.0,
        allow_partial_success=False,
        enable_timeout_chunk_downshift=True,
        chunk_target_records=0,
        chunk_min_records=10,
        chunk_downshift_factor=0.5,
        max_chunk_splits=4,
        max_total_chunks=10,
        runner_fn=runner_fn,
    )

    assert effective_success is False
    assert raw_success is False
    assert result.failure_class == "http_5xx"
    assert chunking_summary["split_count"] == 0
    assert chunking_summary["completed_chunk_count"] == 1
    assert latency_profile["attempt_count"] == 1
