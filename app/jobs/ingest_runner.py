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
    retryable: bool
    error: str | None = None


@dataclass
class IngestRunnerResult:
    success: bool
    attempts: list[AttemptLog]
    run_ids: list[int]
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": [asdict(item) for item in self.attempts],
            "run_ids": self.run_ids,
            "finished_at": self.finished_at,
        }


RequestFn = Callable[[str, dict[str, str], dict[str, Any], float], httpx.Response]


def default_request_fn(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> httpx.Response:
    return httpx.post(url, headers=headers, json=payload, timeout=timeout)


def _is_retryable(http_status: int | None, job_status: str | None, error: str | None) -> bool:
    if error is not None:
        return True
    if http_status is None:
        return True
    if http_status in {408, 429}:
        return True
    if http_status >= 500:
        return True
    if job_status in {"partial_success", "failed"}:
        return True
    return False


def run_ingest_with_retry(
    *,
    api_base_url: str,
    token: str,
    payload: dict[str, Any],
    max_retries: int = 2,
    backoff_seconds: float = 1.0,
    request_timeout: float = 30.0,
    request_fn: RequestFn = default_request_fn,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> IngestRunnerResult:
    max_attempts = max(1, max_retries + 1)
    url = api_base_url.rstrip("/") + "/api/v1/jobs/run-ingest"
    headers = {"Authorization": f"Bearer {token}"}
    attempts: list[AttemptLog] = []
    run_ids: list[int] = []

    for attempt in range(1, max_attempts + 1):
        http_status: int | None = None
        job_status: str | None = None
        error: str | None = None
        try:
            response = request_fn(url, headers, payload, request_timeout)
            http_status = response.status_code
            body = response.json()
            job_status = body.get("status")
            run_id = body.get("run_id")
            if isinstance(run_id, int):
                run_ids.append(run_id)
        except Exception as exc:  # noqa: BLE001
            error = f"{exc.__class__.__name__}: {exc}"

        retryable = _is_retryable(http_status, job_status, error)
        attempts.append(
            AttemptLog(
                attempt=attempt,
                http_status=http_status,
                job_status=job_status,
                retryable=retryable,
                error=error,
            )
        )

        if error is None and http_status == 200 and job_status == "success":
            return IngestRunnerResult(success=True, attempts=attempts, run_ids=run_ids, finished_at=utc_now())

        if attempt < max_attempts and retryable:
            sleep_fn(backoff_seconds * attempt)

    return IngestRunnerResult(success=False, attempts=attempts, run_ids=run_ids, finished_at=utc_now())


def write_runner_report(path: str | Path, result: IngestRunnerResult) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
