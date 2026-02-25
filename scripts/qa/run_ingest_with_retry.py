#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.jobs.ingest_runner import run_ingest_with_retry, write_runner_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ingest job API with retry")
    parser.add_argument("--api-base", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--input", default="data/sample_ingest.json")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--backoff-seconds", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--timeout-scale-on-timeout", type=float, default=1.5)
    parser.add_argument("--timeout-max", type=float, default=360.0)
    parser.add_argument("--heartbeat-interval-seconds", type=float, default=30.0)
    parser.add_argument("--report", default="data/ingest_retry_report.json")
    parser.add_argument("--classification-artifact", default=None)
    parser.add_argument("--dead-letter-dir", default="data/dead_letter")
    parser.add_argument("--disable-dead-letter", action="store_true")
    parser.add_argument("--allow-partial-success", action="store_true")
    return parser.parse_args()


def _utc_timestamp_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_filename_fragment(value: str | None) -> str:
    token = (value or "unknown").strip().lower()
    token = re.sub(r"[^a-z0-9]+", "_", token)
    return token.strip("_") or "unknown"


def _payload_digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def write_dead_letter_record(
    *,
    dead_letter_dir: str | Path,
    source_input_path: str,
    payload: dict,
    result,
    report_path: str,
) -> Path:
    out_dir = Path(dead_letter_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    failure_fragment = _safe_filename_fragment(result.failure_type or result.failure_class)
    output_path = out_dir / f"ingest_dead_letter_{_utc_timestamp_compact()}_{failure_fragment}.json"
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_input_path": source_input_path,
        "report_path": report_path,
        "failure_class": result.failure_class,
        "failure_type": result.failure_type,
        "failure_reason": result.failure_reason,
        "payload_digest": _payload_digest(payload),
        "payload": payload,
        "status": "pending",
    }
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def is_effective_success(result, *, allow_partial_success: bool) -> bool:
    if result.success:
        return True
    if allow_partial_success and result.failure_class == "job_partial_success":
        return True
    return False


def write_failure_classification_artifact(
    *,
    path: str | Path,
    source_input_path: str,
    payload: dict,
    result,
    success: bool,
    raw_success: bool,
    dead_letter_path: str | None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    failure_counts: dict[str, int] = {}
    timeout_attempts = 0
    for item in result.attempts:
        key = item.failure_class or "none"
        failure_counts[key] = failure_counts.get(key, 0) + 1
        if item.failure_class == "timeout":
            timeout_attempts += 1

    attempt_timeline = [
        {
            "attempt": item.attempt,
            "started_at": item.started_at,
            "finished_at": item.finished_at,
            "duration_seconds": item.duration_seconds,
            "request_timeout_seconds": item.request_timeout_seconds,
            "http_status": item.http_status,
            "job_status": item.job_status,
            "failure_class": item.failure_class,
            "failure_type": item.failure_type,
            "retryable": item.retryable,
            "next_backoff_seconds": item.next_backoff_seconds,
            "error": item.error,
            "detail": item.detail,
        }
        for item in result.attempts
    ]

    artifact = {
        "schema_version": "collector_ingest_failure_classification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_input_path": source_input_path,
        "payload_run_type": payload.get("run_type"),
        "payload_record_count": len(payload.get("records") or []),
        "runner": {
            "success": success,
            "raw_success": raw_success,
            "attempt_count": len(result.attempts),
            "run_ids": result.run_ids,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "elapsed_seconds": result.elapsed_seconds,
            "failure_class": result.failure_class,
            "failure_type": result.failure_type,
            "failure_reason": result.failure_reason,
            "timeout_attempts": timeout_attempts,
            "failure_class_counts": failure_counts,
        },
        "dead_letter_path": dead_letter_path,
        "attempt_timeline": attempt_timeline,
    }
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    args = parse_args()
    token = os.getenv("INTERNAL_JOB_TOKEN")
    if not token:
        raise RuntimeError("INTERNAL_JOB_TOKEN is required")

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    def _emit_heartbeat(event: dict) -> None:
        print(
            json.dumps(
                {
                    "channel": "ingest_runner_heartbeat",
                    **event,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    started_monotonic = time.monotonic()
    print(
        json.dumps(
            {
                "channel": "ingest_runner_heartbeat",
                "event": "script_start",
                "ts": datetime.now(timezone.utc).isoformat(),
                "source_input_path": args.input,
                "report_path": args.report,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    result = run_ingest_with_retry(
        api_base_url=args.api_base,
        token=token,
        payload=payload,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
        request_timeout=args.timeout,
        timeout_scale_on_timeout=args.timeout_scale_on_timeout,
        timeout_max=args.timeout_max,
        heartbeat_interval_seconds=args.heartbeat_interval_seconds,
        event_log_fn=_emit_heartbeat,
    )
    write_runner_report(args.report, result)
    success = is_effective_success(result, allow_partial_success=args.allow_partial_success)
    output = {
        "success": success,
        "raw_success": result.success,
        "report": args.report,
        "attempt_count": len(result.attempts),
        "failure_class": result.failure_class,
        "failure_type": result.failure_type,
        "failure_reason": result.failure_reason,
    }
    if result.attempts:
        last = result.attempts[-1]
        output["last_attempt"] = {
            "attempt": last.attempt,
            "http_status": last.http_status,
            "job_status": last.job_status,
            "error": last.error,
            "detail": last.detail,
        }
    if success and not result.success:
        output["accepted_partial_success"] = True

    dead_letter_path: str | None = None
    if not success and not args.disable_dead_letter:
        dead_letter_path = write_dead_letter_record(
            dead_letter_dir=args.dead_letter_dir,
            source_input_path=args.input,
            payload=payload,
            result=result,
            report_path=args.report,
        )
        dead_letter_path = str(dead_letter_path)
        output["dead_letter_path"] = dead_letter_path
    if args.classification_artifact:
        artifact_path = write_failure_classification_artifact(
            path=args.classification_artifact,
            source_input_path=args.input,
            payload=payload,
            result=result,
            success=success,
            raw_success=result.success,
            dead_letter_path=dead_letter_path,
        )
        output["classification_artifact"] = str(artifact_path)
    output["elapsed_seconds"] = round(time.monotonic() - started_monotonic, 3)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
