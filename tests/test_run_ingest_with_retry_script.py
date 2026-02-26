from __future__ import annotations

import json
from pathlib import Path

from app.jobs.ingest_runner import AttemptLog, IngestRunnerResult
from scripts.qa.run_ingest_with_retry import (
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
