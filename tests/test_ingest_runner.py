from __future__ import annotations

from dataclasses import dataclass

from app.jobs.ingest_runner import run_ingest_with_retry


@dataclass
class DummyResponse:
    status_code: int
    body: dict

    def json(self):
        return self.body


def test_ingest_runner_success_without_retry():
    calls = {"count": 0}

    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        return DummyResponse(status_code=200, body={"run_id": 1, "status": "success"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=2,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is True
    assert calls["count"] == 1
    assert result.run_ids == [1]
    assert result.failure_class is None
    assert result.failure_type is None
    assert result.cause_code is None
    assert result.failure_reason is None


def test_ingest_runner_retries_then_succeeds():
    calls = {"count": 0}

    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return DummyResponse(status_code=200, body={"run_id": 10, "status": "partial_success"})
        return DummyResponse(status_code=200, body={"run_id": 11, "status": "success"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=2,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is True
    assert calls["count"] == 2
    assert result.run_ids == [10, 11]
    assert result.attempts[0].retryable is True
    assert result.attempts[0].failure_class == "job_partial_success"
    assert result.failure_class is None
    assert result.failure_type is None
    assert result.cause_code is None
    assert result.failure_reason is None


def test_ingest_runner_fails_after_retries():
    calls = {"count": 0}

    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        return DummyResponse(status_code=500, body={"detail": "server error"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=2,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is False
    assert calls["count"] == 3
    assert result.failure_class == "http_5xx"
    assert result.failure_type == "http_5xx"
    assert result.cause_code == "http_500"
    assert result.failure_reason == "http_5xx: http_status=500 (server error)"


def test_ingest_runner_does_not_retry_on_422_contract_error():
    calls = {"count": 0}

    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        return DummyResponse(status_code=422, body={"detail": "payload schema mismatch"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=2,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is False
    assert calls["count"] == 1
    assert result.failure_class == "payload_contract_422"
    assert result.failure_type == "http_4xx"
    assert result.cause_code == "schema_payload_contract_422"
    assert result.attempts[0].retryable is False
    assert result.attempts[0].failure_type == "http_4xx"
    assert result.failure_reason == "payload_contract_422: http_status=422 (payload schema mismatch)"


def test_ingest_runner_scales_timeout_after_timeout_failure():
    calls = {"count": 0}
    observed_timeouts: list[float] = []

    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        observed_timeouts.append(timeout)
        if calls["count"] == 1:
            raise TimeoutError("timed out")
        return DummyResponse(status_code=200, body={"run_id": 12, "status": "success"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=1,
        request_timeout=100.0,
        timeout_scale_on_timeout=1.5,
        timeout_max=300.0,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is True
    assert calls["count"] == 2
    assert observed_timeouts == [100.0, 150.0]
    assert result.attempts[0].failure_class == "timeout"
    assert result.attempts[0].failure_type == "timeout"
    assert result.attempts[0].cause_code == "timeout_request"
    assert result.attempts[0].request_timeout_seconds == 100.0
    assert result.attempts[1].request_timeout_seconds == 150.0


def test_ingest_runner_classifies_db_auth_detail() -> None:
    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        return DummyResponse(status_code=503, body={"detail": "database connection failed (auth_failed)"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=0,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is False
    assert result.failure_class == "http_5xx"
    assert result.cause_code == "db_auth_failed"
    assert result.attempts[0].cause_code == "db_auth_failed"


def test_ingest_runner_classifies_db_schema_detail() -> None:
    def request_fn(url, headers, payload, timeout):  # noqa: ARG001
        return DummyResponse(status_code=503, body={"detail": "database schema mismatch detected"})

    result = run_ingest_with_retry(
        api_base_url="http://127.0.0.1:8100",
        token="token",
        payload={"records": []},
        max_retries=0,
        request_fn=request_fn,
        sleep_fn=lambda _: None,
    )

    assert result.success is False
    assert result.failure_class == "http_5xx"
    assert result.cause_code == "db_schema_mismatch"
    assert result.attempts[0].cause_code == "db_schema_mismatch"
