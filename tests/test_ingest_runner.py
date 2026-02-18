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
