#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
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
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--report", default="data/ingest_retry_report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv("INTERNAL_JOB_TOKEN")
    if not token:
        raise RuntimeError("INTERNAL_JOB_TOKEN is required")

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run_ingest_with_retry(
        api_base_url=args.api_base,
        token=token,
        payload=payload,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
        request_timeout=args.timeout,
    )
    write_runner_report(args.report, result)
    print(json.dumps({"success": result.success, "report": args.report}, ensure_ascii=False))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
