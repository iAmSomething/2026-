from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AttemptLog:
    attempt: int
    http_status: int | None
    job_status: str | None
    failure_class: str | None
    failure_type: str | None
    retryable: bool
    request_timeout_seconds: float
    error: str | None = None
    detail: str | None = None


@dataclass
class IngestRunnerResult:
    success: bool
    attempts: list[AttemptLog]
    run_ids: list[int]
    finished_at: str
    failure_class: str | None = None
    failure_type: str | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": [asdict(item) for item in self.attempts],
            "run_ids": self.run_ids,
            "finished_at": self.finished_at,
            "failure_class": self.failure_class,
            "failure_type": self.failure_type,
            "failure_reason": self.failure_reason,
        }


RequestFn = Callable[[str, dict[str, str], dict[str, Any], float], httpx.Response]


def default_request_fn(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    return httpx.post(url, headers=headers, json=payload, timeout=timeout)


def _classify_failure(
    http_status: int | None,
    job_status: str | None,
    error: str | None,
) -> str | None:
    if error is not None:
        lowered = error.lower()
        if "timeout" in lowered:
            return "timeout"
        return "request_error"

    if http_status is None:
        return "request_error"

    if http_status == 422:
        return "payload_contract_422"
    if http_status == 408:
        return "http_408"
    if http_status == 429:
        return "http_429"
    if 400 <= http_status < 500:
        return "http_4xx"
    if http_status >= 500:
        return "http_5xx"

    if job_status == "success":
        return None
    if job_status == "partial_success":
        return "job_partial_success"
    if job_status == "failed":
        return "job_failed"
    return "unknown_failure"


def _is_retryable_failure_class(failure_class: str | None) -> bool:
    if failure_class is None:
        return False
    if failure_class in {"payload_contract_422", "http_4xx"}:
        return False
    return True


def _to_failure_type(failure_class: str | None) -> str | None:
    if failure_class is None:
        return None
    if failure_class == "timeout":
        return "timeout"
    if failure_class in {"payload_contract_422", "http_408", "http_429", "http_4xx"}:
        return "http_4xx"
    if failure_class == "http_5xx":
        return "http_5xx"
    return failure_class


def _next_backoff_seconds(failure_class: str | None, base_backoff_seconds: float, attempt: int) -> float:
    step = max(0.0, base_backoff_seconds) * max(1, attempt)
    if failure_class == "timeout":
        return max(step, 5.0)
    if failure_class in {"http_408", "http_429", "http_5xx", "request_error"}:
        return max(step, 2.0)
    return step


def _to_error_detail(body: Any) -> str | None:
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("error")
        if detail is None:
            return None
        if isinstance(detail, str):
            return detail
        return str(detail)
    if isinstance(body, list):
        return str(body[:3])
    if body is None:
        return None
    return str(body)


def _derive_failure_reason(attempts: list[AttemptLog]) -> str:
    if not attempts:
        return "no_attempts"

    last = attempts[-1]
    prefix = last.failure_class or "unknown_failure"
    if last.error:
        return f"{prefix}: {last.error}"
    if last.http_status is not None and last.http_status != 200:
        if last.detail:
            return f"{prefix}: http_status={last.http_status} ({last.detail})"
        return f"{prefix}: http_status={last.http_status}"
    if last.job_status:
        if last.detail:
            return f"{prefix}: job_status={last.job_status} ({last.detail})"
        return f"{prefix}: job_status={last.job_status}"
    return "unknown_failure"


def run_ingest_with_retry(
    *,
    api_base_url: str,
    token: str,
    payload: dict[str, Any],
    max_retries: int = 2,
    backoff_seconds: float = 1.0,
    request_timeout: float = 30.0,
    timeout_scale_on_timeout: float = 1.5,
    timeout_max: float = 600.0,
    request_fn: RequestFn = default_request_fn,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> IngestRunnerResult:
    max_attempts = max(1, max_retries + 1)
    url = api_base_url.rstrip("/") + "/api/v1/jobs/run-ingest"
    headers = {"Authorization": f"Bearer {token}"}
    attempts: list[AttemptLog] = []
    run_ids: list[int] = []
    current_timeout = max(1.0, request_timeout)
    timeout_scale = max(1.0, timeout_scale_on_timeout)
    timeout_ceiling = max(current_timeout, timeout_max)

    for attempt in range(1, max_attempts + 1):
        http_status: int | None = None
        job_status: str | None = None
        error: str | None = None
        detail: str | None = None
        try:
            response = request_fn(url, headers, payload, current_timeout)
            http_status = response.status_code
            try:
                body = response.json()
            except Exception:  # noqa: BLE001
                body = {"detail": response.text[:300] if hasattr(response, "text") else "non-json response"}
            job_status = body.get("status")
            detail = _to_error_detail(body)
            run_id = body.get("run_id")
            if isinstance(run_id, int):
                run_ids.append(run_id)
        except Exception as exc:  # noqa: BLE001
            error = f"{exc.__class__.__name__}: {exc}"

        failure_class = _classify_failure(http_status, job_status, error)
        retryable = _is_retryable_failure_class(failure_class)
        attempts.append(
            AttemptLog(
                attempt=attempt,
                http_status=http_status,
                job_status=job_status,
                failure_class=failure_class,
                failure_type=_to_failure_type(failure_class),
                retryable=retryable,
                request_timeout_seconds=current_timeout,
                error=error,
                detail=detail,
            )
        )

        if error is None and http_status == 200 and job_status == "success":
            return IngestRunnerResult(
                success=True,
                attempts=attempts,
                run_ids=run_ids,
                finished_at=utc_now(),
                failure_class=None,
                failure_type=None,
                failure_reason=None,
            )

        if not retryable:
            break

        if attempt < max_attempts and retryable:
            sleep_fn(_next_backoff_seconds(failure_class, backoff_seconds, attempt))
            if failure_class == "timeout":
                current_timeout = min(current_timeout * timeout_scale, timeout_ceiling)

    return IngestRunnerResult(
        success=False,
        attempts=attempts,
        run_ids=run_ids,
        finished_at=utc_now(),
        failure_class=attempts[-1].failure_class if attempts else None,
        failure_type=attempts[-1].failure_type if attempts else None,
        failure_reason=_derive_failure_reason(attempts),
    )


def write_runner_report(path: str | Path, result: IngestRunnerResult) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
