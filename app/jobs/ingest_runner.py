from __future__ import annotations

import json
import threading
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
    cause_code: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    next_backoff_seconds: float | None = None


@dataclass
class IngestRunnerResult:
    success: bool
    attempts: list[AttemptLog]
    run_ids: list[int]
    finished_at: str
    started_at: str | None = None
    elapsed_seconds: float | None = None
    failure_class: str | None = None
    failure_type: str | None = None
    cause_code: str | None = None
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": [asdict(item) for item in self.attempts],
            "run_ids": self.run_ids,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
            "failure_class": self.failure_class,
            "failure_type": self.failure_type,
            "cause_code": self.cause_code,
            "failure_reason": self.failure_reason,
        }


RequestFn = Callable[[str, dict[str, str], dict[str, Any], float], httpx.Response]
EventLogFn = Callable[[dict[str, Any]], None]


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


def _derive_cause_code(
    *,
    failure_class: str | None,
    http_status: int | None,
    detail: str | None,
    error: str | None,
) -> str | None:
    lowered_detail = (detail or "").lower()
    lowered_error = (error or "").lower()

    if failure_class == "timeout":
        return "timeout_request"
    if "timeout" in lowered_error:
        return "timeout_request"
    if "database settings are not configured" in lowered_detail or "database is not configured" in lowered_detail:
        return "db_config_missing"
    if "database_url is empty" in lowered_detail:
        return "db_config_missing"
    if "database schema mismatch" in lowered_detail or "schema auto-healed" in lowered_detail:
        return "db_schema_mismatch"
    if failure_class == "payload_contract_422":
        return "schema_payload_contract_422"

    if "database connection failed" in lowered_detail:
        if "(auth_failed)" in lowered_detail or "(auth_error)" in lowered_detail:
            return "db_auth_failed"
        if "(network_timeout)" in lowered_detail:
            return "db_timeout"
        if "(invalid_host_or_uri)" in lowered_detail:
            return "db_uri_invalid"
        if "(connection_refused)" in lowered_detail or "(network_error)" in lowered_detail:
            return "db_network_error"
        if "(ssl_required)" in lowered_detail:
            return "db_ssl_required"
        if "(unknown)" in lowered_detail:
            return "db_connection_unknown"
        return "db_connection_error"

    if "database query failed" in lowered_detail and "(" in lowered_detail and ")" in lowered_detail:
        return "db_query_error"
    if "database query failed" in lowered_detail:
        return "db_query_error"

    if failure_class in {"http_408", "http_429"}:
        return "http_retryable_client"
    if failure_class == "http_5xx" and http_status is not None:
        return f"http_{http_status}"
    if failure_class == "http_5xx":
        return "http_5xx"
    if failure_class == "request_error":
        return "request_error"
    if failure_class == "http_4xx":
        return "http_4xx"
    if failure_class == "job_partial_success":
        return "job_partial_success"
    if failure_class == "job_failed":
        return "job_failed"
    return failure_class


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


def _emit_event(event_log_fn: EventLogFn | None, *, event: str, **fields: Any) -> None:
    if event_log_fn is None:
        return
    payload = {"ts": utc_now(), "event": event, **fields}
    try:
        event_log_fn(payload)
    except Exception:  # noqa: BLE001
        return


def _request_with_optional_heartbeat(
    *,
    request_fn: RequestFn,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    event_log_fn: EventLogFn | None,
    heartbeat_interval_seconds: float,
    attempt: int,
) -> httpx.Response:
    if event_log_fn is None or heartbeat_interval_seconds <= 0:
        return request_fn(url, headers, payload, timeout)

    started = time.monotonic()
    stop_event = threading.Event()

    def _heartbeat() -> None:
        tick = 1
        while not stop_event.wait(heartbeat_interval_seconds):
            elapsed = round(time.monotonic() - started, 3)
            _emit_event(
                event_log_fn,
                event="attempt_waiting",
                attempt=attempt,
                heartbeat_tick=tick,
                elapsed_seconds=elapsed,
                request_timeout_seconds=timeout,
            )
            tick += 1

    thread = threading.Thread(target=_heartbeat, daemon=True)
    thread.start()
    try:
        return request_fn(url, headers, payload, timeout)
    finally:
        stop_event.set()
        thread.join(timeout=0.1)


def run_ingest_with_retry(
    *,
    api_base_url: str,
    token: str,
    payload: dict[str, Any],
    max_retries: int = 2,
    backoff_seconds: float = 1.0,
    request_timeout: float = 180.0,
    timeout_scale_on_timeout: float = 1.5,
    timeout_max: float = 360.0,
    heartbeat_interval_seconds: float = 30.0,
    request_fn: RequestFn = default_request_fn,
    sleep_fn: Callable[[float], None] = time.sleep,
    event_log_fn: EventLogFn | None = None,
) -> IngestRunnerResult:
    run_started_at = utc_now()
    run_started_monotonic = time.monotonic()
    max_attempts = max(1, max_retries + 1)
    url = api_base_url.rstrip("/") + "/api/v1/jobs/run-ingest"
    headers = {"Authorization": f"Bearer {token}"}
    attempts: list[AttemptLog] = []
    run_ids: list[int] = []
    current_timeout = max(1.0, request_timeout)
    timeout_scale = max(1.0, timeout_scale_on_timeout)
    timeout_ceiling = max(current_timeout, timeout_max)
    _emit_event(
        event_log_fn,
        event="run_start",
        api_base_url=api_base_url,
        max_attempts=max_attempts,
        max_retries=max_retries,
        initial_request_timeout_seconds=current_timeout,
        timeout_max_seconds=timeout_ceiling,
    )

    for attempt in range(1, max_attempts + 1):
        attempt_started_at = utc_now()
        attempt_started_monotonic = time.monotonic()
        http_status: int | None = None
        job_status: str | None = None
        error: str | None = None
        detail: str | None = None
        _emit_event(
            event_log_fn,
            event="attempt_start",
            attempt=attempt,
            max_attempts=max_attempts,
            request_timeout_seconds=current_timeout,
        )
        try:
            response = _request_with_optional_heartbeat(
                request_fn=request_fn,
                url=url,
                headers=headers,
                payload=payload,
                timeout=current_timeout,
                event_log_fn=event_log_fn,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
                attempt=attempt,
            )
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

        attempt_finished_at = utc_now()
        attempt_duration = round(time.monotonic() - attempt_started_monotonic, 3)
        failure_class = _classify_failure(http_status, job_status, error)
        cause_code = _derive_cause_code(
            failure_class=failure_class,
            http_status=http_status,
            detail=detail,
            error=error,
        )
        retryable = _is_retryable_failure_class(failure_class)
        next_backoff_seconds = (
            _next_backoff_seconds(failure_class, backoff_seconds, attempt)
            if attempt < max_attempts and retryable
            else None
        )
        attempts.append(
            AttemptLog(
                attempt=attempt,
                http_status=http_status,
                job_status=job_status,
                failure_class=failure_class,
                failure_type=_to_failure_type(failure_class),
                cause_code=cause_code,
                retryable=retryable,
                request_timeout_seconds=current_timeout,
                error=error,
                detail=detail,
                started_at=attempt_started_at,
                finished_at=attempt_finished_at,
                duration_seconds=attempt_duration,
                next_backoff_seconds=next_backoff_seconds,
            )
        )
        _emit_event(
            event_log_fn,
            event="attempt_result",
            attempt=attempt,
            http_status=http_status,
            job_status=job_status,
            failure_class=failure_class,
            failure_type=_to_failure_type(failure_class),
            cause_code=cause_code,
            retryable=retryable,
            duration_seconds=attempt_duration,
            next_backoff_seconds=next_backoff_seconds,
            error=error,
            detail=detail,
        )

        if error is None and http_status == 200 and job_status == "success":
            elapsed_seconds = round(time.monotonic() - run_started_monotonic, 3)
            _emit_event(
                event_log_fn,
                event="run_end",
                success=True,
                elapsed_seconds=elapsed_seconds,
                attempt_count=len(attempts),
            )
            return IngestRunnerResult(
                success=True,
                attempts=attempts,
                run_ids=run_ids,
                started_at=run_started_at,
                finished_at=utc_now(),
                elapsed_seconds=elapsed_seconds,
                failure_class=None,
                failure_type=None,
                cause_code=None,
                failure_reason=None,
            )

        if not retryable:
            break

        if attempt < max_attempts and retryable:
            backoff_wait = _next_backoff_seconds(failure_class, backoff_seconds, attempt)
            _emit_event(
                event_log_fn,
                event="retry_wait",
                attempt=attempt,
                backoff_seconds=backoff_wait,
                next_attempt=attempt + 1,
            )
            sleep_fn(backoff_wait)
            if failure_class == "timeout":
                prev_timeout = current_timeout
                current_timeout = min(current_timeout * timeout_scale, timeout_ceiling)
                _emit_event(
                    event_log_fn,
                    event="timeout_scaled",
                    attempt=attempt + 1,
                    previous_request_timeout_seconds=prev_timeout,
                    next_request_timeout_seconds=current_timeout,
                )

    elapsed_seconds = round(time.monotonic() - run_started_monotonic, 3)
    failure_reason = _derive_failure_reason(attempts)
    _emit_event(
        event_log_fn,
        event="run_end",
        success=False,
        elapsed_seconds=elapsed_seconds,
        attempt_count=len(attempts),
        failure_class=attempts[-1].failure_class if attempts else None,
        failure_type=attempts[-1].failure_type if attempts else None,
        cause_code=attempts[-1].cause_code if attempts else None,
        failure_reason=failure_reason,
    )
    return IngestRunnerResult(
        success=False,
        attempts=attempts,
        run_ids=run_ids,
        started_at=run_started_at,
        finished_at=utc_now(),
        elapsed_seconds=elapsed_seconds,
        failure_class=attempts[-1].failure_class if attempts else None,
        failure_type=attempts[-1].failure_type if attempts else None,
        cause_code=attempts[-1].cause_code if attempts else None,
        failure_reason=failure_reason,
    )


def write_runner_report(path: str | Path, result: IngestRunnerResult) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
