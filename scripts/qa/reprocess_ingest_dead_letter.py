#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.jobs.ingest_runner import IngestRunnerResult, run_ingest_with_retry, write_runner_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reprocess ingest dead-letter payload")
    parser.add_argument("--api-base", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--dead-letter", default=None, help="dead-letter json path")
    parser.add_argument("--dead-letter-dir", default="data/dead_letter")
    parser.add_argument("--latest", action="store_true", help="use latest file from dead-letter dir")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--backoff-seconds", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--timeout-scale-on-timeout", type=float, default=1.5)
    parser.add_argument("--timeout-max", type=float, default=360.0)
    parser.add_argument("--report", default="data/reprocess_ingest_dead_letter_report.json")
    return parser.parse_args()


def resolve_dead_letter_path(*, dead_letter: str | None, dead_letter_dir: str, latest: bool) -> Path:
    if dead_letter:
        return Path(dead_letter)
    if latest:
        files = sorted(Path(dead_letter_dir).glob("ingest_dead_letter_*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            raise FileNotFoundError(f"no dead-letter files found in {dead_letter_dir}")
        return files[-1]
    raise ValueError("either --dead-letter or --latest must be provided")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reprocess_dead_letter_record(
    *,
    dead_letter_path: str | Path,
    api_base_url: str,
    token: str,
    report_path: str,
    max_retries: int,
    backoff_seconds: float,
    timeout: float,
    timeout_scale_on_timeout: float,
    timeout_max: float,
    runner_fn: Callable[..., IngestRunnerResult] = run_ingest_with_retry,
) -> IngestRunnerResult:
    path = Path(dead_letter_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("dead-letter payload must be an object")

    result = runner_fn(
        api_base_url=api_base_url,
        token=token,
        payload=payload,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        request_timeout=timeout,
        timeout_scale_on_timeout=timeout_scale_on_timeout,
        timeout_max=timeout_max,
    )
    write_runner_report(report_path, result)

    attempt = {
        "reprocessed_at": _utc_now(),
        "success": result.success,
        "failure_class": result.failure_class,
        "failure_type": result.failure_type,
        "failure_reason": result.failure_reason,
        "report_path": report_path,
    }
    attempts = record.get("reprocess_attempts")
    if not isinstance(attempts, list):
        attempts = []
    attempts.append(attempt)
    record["reprocess_attempts"] = attempts
    record["last_reprocess_report"] = report_path
    record["status"] = "resolved" if result.success else "pending"
    if result.success:
        record["resolved_at"] = _utc_now()
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return result


def main() -> int:
    args = parse_args()
    token = os.getenv("INTERNAL_JOB_TOKEN")
    if not token:
        raise RuntimeError("INTERNAL_JOB_TOKEN is required")

    dead_letter_path = resolve_dead_letter_path(
        dead_letter=args.dead_letter,
        dead_letter_dir=args.dead_letter_dir,
        latest=args.latest,
    )
    result = reprocess_dead_letter_record(
        dead_letter_path=dead_letter_path,
        api_base_url=args.api_base,
        token=token,
        report_path=args.report,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
        timeout=args.timeout,
        timeout_scale_on_timeout=args.timeout_scale_on_timeout,
        timeout_max=args.timeout_max,
    )
    output = {
        "dead_letter_path": str(dead_letter_path),
        "success": result.success,
        "report": args.report,
        "failure_class": result.failure_class,
        "failure_type": result.failure_type,
        "failure_reason": result.failure_reason,
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
