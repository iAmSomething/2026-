#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class StepResult:
    name: str
    mode: str
    command: list[str] | None
    status: str
    exit_code: int | None
    output_path: str | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ops recovery bundle (ingest retry + single matchup reprocess + capture)")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--api-base", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--matchup-id", default=None)
    parser.add_argument("--poll-fingerprint", default=None)
    parser.add_argument("--input", default="data/sample_ingest.json")
    parser.add_argument("--output-dir", default="data/ops_recovery_bundle")
    parser.add_argument("--report", default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-reprocess", action="store_true")
    parser.add_argument("--skip-capture", action="store_true")
    parser.add_argument("--capture-timeout", type=float, default=10.0)
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_command(command: list[str]) -> tuple[int, str | None]:
    proc = subprocess.run(command, capture_output=True, text=True)  # noqa: S603
    detail = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, detail.strip() or None


def build_ingest_command(*, api_base: str, input_path: str, report_path: Path) -> list[str]:
    return [
        sys.executable,
        "scripts/qa/run_ingest_with_retry.py",
        "--api-base",
        api_base,
        "--input",
        input_path,
        "--report",
        str(report_path),
    ]


def build_reprocess_command(
    *,
    matchup_id: str | None,
    poll_fingerprint: str | None,
    mode: str,
    output_dir: Path,
    report_path: Path,
) -> list[str]:
    command = [
        sys.executable,
        "scripts/qa/reprocess_single_matchup.py",
        "--mode",
        mode,
        "--output-dir",
        str(output_dir),
        "--report",
        str(report_path),
    ]
    if matchup_id:
        command.extend(["--matchup-id", matchup_id])
    if poll_fingerprint:
        command.extend(["--poll-fingerprint", poll_fingerprint])
    return command


def run_step(*, name: str, mode: str, command: list[str], output_path: Path | None = None) -> StepResult:
    if mode == "dry-run":
        return StepResult(
            name=name,
            mode=mode,
            command=command,
            status="planned",
            exit_code=None,
            output_path=str(output_path) if output_path else None,
        )

    code, detail = _run_command(command)
    return StepResult(
        name=name,
        mode=mode,
        command=command,
        status="success" if code == 0 else "failed",
        exit_code=code,
        output_path=str(output_path) if output_path else None,
        error=None if code == 0 else detail,
    )


def capture_endpoints(*, api_base: str, matchup_id: str | None, timeout: float, output_dir: Path, mode: str) -> StepResult:
    capture_path = output_dir / "api_capture.json"
    urls = {
        "health": f"{api_base.rstrip('/')}/health",
        "summary": f"{api_base.rstrip('/')}/api/v1/dashboard/summary",
    }
    if matchup_id:
        urls["matchup"] = f"{api_base.rstrip('/')}/api/v1/matchups/{matchup_id}"

    if mode == "dry-run":
        return StepResult(
            name="capture",
            mode=mode,
            command=None,
            status="planned",
            exit_code=None,
            output_path=str(capture_path),
        )

    payload: dict[str, Any] = {"captured_at": _utc_now(), "targets": {}}
    try:
        for key, url in urls.items():
            with urlopen(url, timeout=timeout) as res:  # noqa: S310
                raw = res.read().decode("utf-8")
                payload["targets"][key] = {
                    "url": url,
                    "status": int(getattr(res, "status", 200)),
                    "body": raw,
                }
    except URLError as exc:
        return StepResult(
            name="capture",
            mode=mode,
            command=None,
            status="failed",
            exit_code=1,
            output_path=str(capture_path),
            error=str(exc),
        )

    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return StepResult(
        name="capture",
        mode=mode,
        command=None,
        status="success",
        exit_code=0,
        output_path=str(capture_path),
    )


def build_ops_checklist(*, step_results: list[StepResult]) -> list[str]:
    checklist = [
        "1) preflight: DATABASE_URL/INTERNAL_JOB_TOKEN set 확인",
        "2) ingest 재실행(run_ingest_with_retry) 결과 확인",
        "3) 단일 매치업 재처리(reprocess_single_matchup) 결과 확인",
        "4) health/summary/matchup 캡처 결과 확인",
    ]

    failures = {step.name: step for step in step_results if step.status == "failed"}
    if "ingest" in failures:
        checklist.append("retry-guide: ingest 실패 시 backoff/timeout 상향 후 1회 재시도하고 dead-letter/classification artifact 확인")
    if "reprocess" in failures:
        checklist.append("rollback-guide: reprocess 실패 시 dry-run으로 payload/snapshot 재생성 후 대상 matchup_id/poll_fingerprint 재확인")
    if "capture" in failures:
        checklist.append("rollback-guide: capture 실패 시 /health 복구 후 요약 API부터 순차 검증")
    return checklist


def run_bundle(args: argparse.Namespace) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    step_results: list[StepResult] = []

    if not args.skip_ingest:
        ingest_report = out_dir / "ingest_retry_report.json"
        ingest_cmd = build_ingest_command(api_base=args.api_base, input_path=args.input, report_path=ingest_report)
        ingest_result = run_step(name="ingest", mode=args.mode, command=ingest_cmd, output_path=ingest_report)
        step_results.append(ingest_result)
        if ingest_result.status == "failed" and not args.continue_on_error:
            pass

    if not args.skip_reprocess and (args.matchup_id or args.poll_fingerprint):
        reprocess_report = out_dir / "reprocess_report.json"
        reprocess_cmd = build_reprocess_command(
            matchup_id=args.matchup_id,
            poll_fingerprint=args.poll_fingerprint,
            mode=args.mode,
            output_dir=out_dir,
            report_path=reprocess_report,
        )
        reprocess_result = run_step(name="reprocess", mode=args.mode, command=reprocess_cmd, output_path=reprocess_report)
        step_results.append(reprocess_result)
        if reprocess_result.status == "failed" and not args.continue_on_error:
            pass

    if not args.skip_capture:
        capture_result = capture_endpoints(
            api_base=args.api_base,
            matchup_id=args.matchup_id,
            timeout=args.capture_timeout,
            output_dir=out_dir,
            mode=args.mode,
        )
        step_results.append(capture_result)

    checklist = build_ops_checklist(step_results=step_results)

    status = "success"
    if any(step.status == "failed" for step in step_results):
        status = "failed"
    elif any(step.status == "planned" for step in step_results):
        status = "dry-run"

    summary = {
        "status": status,
        "mode": args.mode,
        "api_base": args.api_base,
        "matchup_id": args.matchup_id,
        "poll_fingerprint": args.poll_fingerprint,
        "output_dir": str(out_dir),
        "steps": [
            {
                "name": step.name,
                "mode": step.mode,
                "command": step.command,
                "status": step.status,
                "exit_code": step.exit_code,
                "output_path": step.output_path,
                "error": step.error,
            }
            for step in step_results
        ],
        "ops_checklist": checklist,
        "generated_at": _utc_now(),
    }
    report_path = Path(args.report) if args.report else out_dir / "recovery_bundle_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["report_path"] = str(report_path)
    return summary


def main() -> int:
    args = parse_args()
    result = run_bundle(args)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
