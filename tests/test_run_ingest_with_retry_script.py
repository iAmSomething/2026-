from __future__ import annotations

from app.jobs.ingest_runner import AttemptLog, IngestRunnerResult
from scripts.qa.run_ingest_with_retry import is_effective_success


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
                retryable=False,
                request_timeout_seconds=30.0,
            )
        ],
        run_ids=[1],
        finished_at="2026-02-24T00:00:00+00:00",
        failure_class=failure_class,
        failure_type=failure_class,
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
