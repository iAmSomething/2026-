#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.jobs.ingest_runner import IngestRunnerResult, run_ingest_with_retry, write_runner_report


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
    parser.add_argument("--comment-template-path", default=None)
    parser.add_argument("--dead-letter-dir", default="data/dead_letter")
    parser.add_argument("--disable-dead-letter", action="store_true")
    parser.add_argument("--allow-partial-success", action="store_true")

    parser.add_argument("--enable-timeout-chunk-downshift", action="store_true")
    parser.add_argument("--chunk-target-records", type=int, default=0)
    parser.add_argument("--chunk-min-records", type=int, default=20)
    parser.add_argument("--chunk-downshift-factor", type=float, default=0.5)
    parser.add_argument("--max-chunk-splits", type=int, default=8)
    parser.add_argument("--max-total-chunks", type=int, default=20)
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


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    clean = sorted(v for v in values if isinstance(v, (int, float)) and math.isfinite(float(v)))
    if not clean:
        return None
    rank = max(1, math.ceil(len(clean) * percentile))
    return round(float(clean[rank - 1]), 3)


def _build_latency_profile(*, attempt_durations: list[float], chunk_durations: list[float], total_elapsed_seconds: float) -> dict[str, float | None]:
    clean_attempts = [float(v) for v in attempt_durations if isinstance(v, (int, float)) and math.isfinite(float(v))]
    clean_chunks = [float(v) for v in chunk_durations if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return {
        "attempt_count": len(clean_attempts),
        "attempt_avg_seconds": round(sum(clean_attempts) / len(clean_attempts), 3) if clean_attempts else None,
        "attempt_p95_seconds": _nearest_rank(clean_attempts, 0.95),
        "chunk_count": len(clean_chunks),
        "chunk_avg_seconds": round(sum(clean_chunks) / len(clean_chunks), 3) if clean_chunks else None,
        "chunk_p95_seconds": _nearest_rank(clean_chunks, 0.95),
        "total_elapsed_seconds": round(total_elapsed_seconds, 3),
    }


def _clone_payload_with_records(payload: dict[str, Any], records: list[Any]) -> dict[str, Any]:
    chunk_payload = dict(payload)
    chunk_payload["records"] = list(records)
    return chunk_payload


def _build_initial_chunks(records: list[Any], chunk_target_records: int) -> list[list[Any]]:
    if chunk_target_records <= 0 or len(records) <= chunk_target_records:
        return [list(records)]
    chunks: list[list[Any]] = []
    for idx in range(0, len(records), chunk_target_records):
        chunks.append(list(records[idx : idx + chunk_target_records]))
    return chunks or [list(records)]


def _split_records_for_downshift(records: list[Any], factor: float, min_records: int) -> tuple[list[Any], list[Any]] | None:
    if len(records) <= max(1, min_records):
        return None
    bounded_factor = min(max(factor, 0.1), 0.9)
    split_at = int(len(records) * bounded_factor)
    split_at = max(1, min(len(records) - 1, split_at))
    left = records[:split_at]
    right = records[split_at:]
    if not left or not right:
        return None
    return left, right


def _is_timeout_like_failure(result: IngestRunnerResult) -> bool:
    if result.failure_class == "timeout" or result.cause_code == "timeout_request":
        return True
    if not result.attempts:
        return False
    last = result.attempts[-1]
    return last.failure_class == "timeout" or last.cause_code == "timeout_request"


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


def execute_ingest_with_adaptive_chunks(
    *,
    api_base: str,
    token: str,
    payload: dict[str, Any],
    max_retries: int,
    backoff_seconds: float,
    timeout: float,
    timeout_scale_on_timeout: float,
    timeout_max: float,
    heartbeat_interval_seconds: float,
    allow_partial_success: bool,
    enable_timeout_chunk_downshift: bool,
    chunk_target_records: int,
    chunk_min_records: int,
    chunk_downshift_factor: float,
    max_chunk_splits: int,
    max_total_chunks: int,
    runner_fn: Callable[..., IngestRunnerResult] = run_ingest_with_retry,
    event_log_fn: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[IngestRunnerResult, bool, bool, dict[str, Any], dict[str, Any]]:
    records = list(payload.get("records") or [])
    if not records:
        result = runner_fn(
            api_base_url=api_base,
            token=token,
            payload=payload,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            request_timeout=timeout,
            timeout_scale_on_timeout=timeout_scale_on_timeout,
            timeout_max=timeout_max,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            event_log_fn=event_log_fn,
        )
        effective = is_effective_success(result, allow_partial_success=allow_partial_success)
        chunking_summary = {
            "enabled": bool(enable_timeout_chunk_downshift),
            "initial_record_count": 0,
            "initial_chunk_count": 1,
            "completed_chunk_count": 1,
            "split_count": 0,
            "max_queue_depth": 1,
            "chunk_target_records": chunk_target_records,
            "chunk_min_records": chunk_min_records,
            "chunk_downshift_factor": chunk_downshift_factor,
            "max_chunk_splits": max_chunk_splits,
            "max_total_chunks": max_total_chunks,
            "chunks": [
                {
                    "chunk_index": 1,
                    "record_count": 0,
                    "effective_success": effective,
                    "raw_success": result.success,
                    "failure_class": result.failure_class,
                    "cause_code": result.cause_code,
                    "attempt_count": len(result.attempts),
                    "elapsed_seconds": result.elapsed_seconds,
                    "timeout_attempts": sum(1 for item in result.attempts if item.failure_class == "timeout" or item.cause_code == "timeout_request"),
                }
            ],
            "split_events": [],
            "terminated_on_chunk": None if effective else 1,
        }
        profile = _build_latency_profile(
            attempt_durations=[item.duration_seconds for item in result.attempts if item.duration_seconds is not None],
            chunk_durations=[result.elapsed_seconds or 0.0],
            total_elapsed_seconds=result.elapsed_seconds or 0.0,
        )
        return result, effective, result.success, chunking_summary, profile

    started_monotonic = time.monotonic()
    queue = _build_initial_chunks(records, chunk_target_records)
    max_queue_depth = len(queue)
    chunks: list[dict[str, Any]] = []
    split_events: list[dict[str, Any]] = []
    split_count = 0

    aggregated_attempts = []
    aggregated_run_ids: list[int] = []
    chunk_elapsed: list[float] = []
    raw_success_all = True
    terminal_result: IngestRunnerResult | None = None
    chunk_index = 0

    while queue:
        max_queue_depth = max(max_queue_depth, len(queue))
        chunk_records = queue.pop(0)
        chunk_index += 1

        chunk_payload = _clone_payload_with_records(payload, chunk_records)
        chunk_result = runner_fn(
            api_base_url=api_base,
            token=token,
            payload=chunk_payload,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            request_timeout=timeout,
            timeout_scale_on_timeout=timeout_scale_on_timeout,
            timeout_max=timeout_max,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            event_log_fn=event_log_fn,
        )
        chunk_effective_success = is_effective_success(chunk_result, allow_partial_success=allow_partial_success)
        timeout_attempts = sum(
            1
            for item in chunk_result.attempts
            if item.failure_class == "timeout" or item.cause_code == "timeout_request"
        )

        aggregated_attempts.extend(chunk_result.attempts)
        aggregated_run_ids.extend(chunk_result.run_ids)
        if chunk_result.elapsed_seconds is not None:
            chunk_elapsed.append(chunk_result.elapsed_seconds)

        chunk_meta = {
            "chunk_index": chunk_index,
            "record_count": len(chunk_records),
            "effective_success": chunk_effective_success,
            "raw_success": chunk_result.success,
            "failure_class": chunk_result.failure_class,
            "failure_type": chunk_result.failure_type,
            "cause_code": chunk_result.cause_code,
            "failure_reason": chunk_result.failure_reason,
            "attempt_count": len(chunk_result.attempts),
            "elapsed_seconds": chunk_result.elapsed_seconds,
            "timeout_attempts": timeout_attempts,
            "run_ids": chunk_result.run_ids,
        }
        chunks.append(chunk_meta)

        if chunk_effective_success:
            raw_success_all = raw_success_all and chunk_result.success
            continue

        can_split = (
            enable_timeout_chunk_downshift
            and _is_timeout_like_failure(chunk_result)
            and len(chunk_records) > max(1, chunk_min_records)
            and split_count < max(0, max_chunk_splits)
            and (len(queue) + 2) <= max(1, max_total_chunks)
        )

        if can_split:
            split_pair = _split_records_for_downshift(
                chunk_records,
                factor=chunk_downshift_factor,
                min_records=chunk_min_records,
            )
            if split_pair is not None:
                left, right = split_pair
                queue = [left, right, *queue]
                split_count += 1
                split_events.append(
                    {
                        "chunk_index": chunk_index,
                        "source_record_count": len(chunk_records),
                        "left_record_count": len(left),
                        "right_record_count": len(right),
                        "reason": "timeout_request",
                    }
                )
                continue

        terminal_result = chunk_result
        raw_success_all = False
        break

    elapsed_seconds = round(time.monotonic() - started_monotonic, 3)

    if terminal_result is not None:
        combined = IngestRunnerResult(
            success=False,
            attempts=aggregated_attempts,
            run_ids=aggregated_run_ids,
            started_at=aggregated_attempts[0].started_at if aggregated_attempts else datetime.now(timezone.utc).isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=elapsed_seconds,
            failure_class=terminal_result.failure_class,
            failure_type=terminal_result.failure_type,
            cause_code=terminal_result.cause_code,
            failure_reason=terminal_result.failure_reason,
        )
        effective_success = False
    else:
        if raw_success_all:
            failure_class = None
            failure_type = None
            cause_code = None
        else:
            failure_class = "job_partial_success"
            failure_type = "job_partial_success"
            cause_code = "job_partial_success"
        combined = IngestRunnerResult(
            success=raw_success_all,
            attempts=aggregated_attempts,
            run_ids=aggregated_run_ids,
            started_at=aggregated_attempts[0].started_at if aggregated_attempts else datetime.now(timezone.utc).isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=elapsed_seconds,
            failure_class=failure_class,
            failure_type=failure_type,
            cause_code=cause_code,
            failure_reason=None,
        )
        effective_success = is_effective_success(combined, allow_partial_success=allow_partial_success)

    chunking_summary = {
        "enabled": bool(enable_timeout_chunk_downshift),
        "initial_record_count": len(records),
        "initial_chunk_count": len(_build_initial_chunks(records, chunk_target_records)),
        "completed_chunk_count": len(chunks),
        "split_count": split_count,
        "max_queue_depth": max_queue_depth,
        "chunk_target_records": chunk_target_records,
        "chunk_min_records": chunk_min_records,
        "chunk_downshift_factor": chunk_downshift_factor,
        "max_chunk_splits": max_chunk_splits,
        "max_total_chunks": max_total_chunks,
        "chunks": chunks,
        "split_events": split_events,
        "terminated_on_chunk": (chunks[-1]["chunk_index"] if terminal_result is not None and chunks else None),
    }
    latency_profile = _build_latency_profile(
        attempt_durations=[item.duration_seconds for item in aggregated_attempts if item.duration_seconds is not None],
        chunk_durations=chunk_elapsed,
        total_elapsed_seconds=elapsed_seconds,
    )
    return combined, effective_success, raw_success_all, chunking_summary, latency_profile


def write_failure_classification_artifact(
    *,
    path: str | Path,
    source_input_path: str,
    payload: dict,
    result,
    success: bool,
    raw_success: bool,
    dead_letter_path: str | None,
    chunking_summary: dict[str, Any] | None = None,
    latency_profile: dict[str, Any] | None = None,
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
            "cause_code": item.cause_code,
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
            "cause_code": result.cause_code,
            "failure_reason": result.failure_reason,
            "timeout_attempts": timeout_attempts,
            "failure_class_counts": failure_counts,
        },
        "dead_letter_path": dead_letter_path,
        "attempt_timeline": attempt_timeline,
    }
    if chunking_summary is not None:
        artifact["chunking_summary"] = chunking_summary
    if latency_profile is not None:
        artifact["latency_profile"] = latency_profile
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def write_failure_comment_template(
    *,
    path: str | Path,
    report_path: str,
    classification_artifact_path: str | None,
    dead_letter_path: str | None,
    result,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_url = (
        f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/"
        f"{os.getenv('GITHUB_REPOSITORY', '')}/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}"
    )
    lines = [
        "[DEVELOP][INGEST FAILURE TEMPLATE]",
        "report_path: develop_report/YYYY-MM-DD_issueNNN_ingest_failure_report.md",
        "evidence:",
        f"- workflow_run: {run_url}",
        f"- ingest_report: `{report_path}`",
    ]
    if classification_artifact_path:
        lines.append(f"- classification_artifact: `{classification_artifact_path}`")
    if dead_letter_path:
        lines.append(f"- dead_letter: `{dead_letter_path}`")
    lines.extend(
        [
            f"- failure_class: `{result.failure_class}`",
            f"- failure_type: `{result.failure_type}`",
            f"- cause_code: `{result.cause_code}`",
            f"- failure_reason: `{result.failure_reason}`",
            "next_status: status/in-progress",
            "",
            "# Summary",
            "1. cause_code 기반으로 DB/Auth/Schema/Timeout 조치 대상을 분리합니다.",
            "2. 동일 유형 재실행에서 cause_code 일치 여부를 확인합니다.",
        ]
    )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
                "record_count": len(payload.get("records") or []),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    result, success, raw_success, chunking_summary, latency_profile = execute_ingest_with_adaptive_chunks(
        api_base=args.api_base,
        token=token,
        payload=payload,
        max_retries=args.max_retries,
        backoff_seconds=args.backoff_seconds,
        timeout=args.timeout,
        timeout_scale_on_timeout=args.timeout_scale_on_timeout,
        timeout_max=args.timeout_max,
        heartbeat_interval_seconds=args.heartbeat_interval_seconds,
        allow_partial_success=args.allow_partial_success,
        enable_timeout_chunk_downshift=args.enable_timeout_chunk_downshift,
        chunk_target_records=args.chunk_target_records,
        chunk_min_records=args.chunk_min_records,
        chunk_downshift_factor=args.chunk_downshift_factor,
        max_chunk_splits=args.max_chunk_splits,
        max_total_chunks=args.max_total_chunks,
        event_log_fn=_emit_heartbeat,
    )

    write_runner_report(args.report, result)
    report_json = json.loads(Path(args.report).read_text(encoding="utf-8"))
    report_json["raw_success"] = raw_success
    report_json["effective_success"] = success
    report_json["chunking"] = chunking_summary
    report_json["latency_profile"] = latency_profile
    Path(args.report).write_text(json.dumps(report_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = {
        "success": success,
        "raw_success": raw_success,
        "report": args.report,
        "attempt_count": len(result.attempts),
        "failure_class": result.failure_class,
        "failure_type": result.failure_type,
        "cause_code": result.cause_code,
        "failure_reason": result.failure_reason,
        "chunking": {
            "initial_record_count": chunking_summary.get("initial_record_count"),
            "initial_chunk_count": chunking_summary.get("initial_chunk_count"),
            "completed_chunk_count": chunking_summary.get("completed_chunk_count"),
            "split_count": chunking_summary.get("split_count"),
            "max_queue_depth": chunking_summary.get("max_queue_depth"),
        },
        "latency_profile": latency_profile,
    }
    if result.attempts:
        last = result.attempts[-1]
        output["last_attempt"] = {
            "attempt": last.attempt,
            "http_status": last.http_status,
            "job_status": last.job_status,
            "cause_code": last.cause_code,
            "error": last.error,
            "detail": last.detail,
        }
    if success and not raw_success:
        output["accepted_partial_success"] = True

    dead_letter_path: str | None = None
    artifact_path: str | None = None
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
        artifact_path = str(
            write_failure_classification_artifact(
                path=args.classification_artifact,
                source_input_path=args.input,
                payload=payload,
                result=result,
                success=success,
                raw_success=raw_success,
                dead_letter_path=dead_letter_path,
                chunking_summary=chunking_summary,
                latency_profile=latency_profile,
            )
        )
        output["classification_artifact"] = artifact_path
    if not success and args.comment_template_path:
        template_path = write_failure_comment_template(
            path=args.comment_template_path,
            report_path=args.report,
            classification_artifact_path=artifact_path,
            dead_letter_path=dead_letter_path,
            result=result,
        )
        output["comment_template_path"] = str(template_path)

    output["elapsed_seconds"] = round(time.monotonic() - started_monotonic, 3)
    print(json.dumps(output, ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
