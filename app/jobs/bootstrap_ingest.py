from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db import get_connection
from app.models.schemas import IngestPayload
from app.services.ingest_service import ingest_payload
from app.services.repository import PostgresRepository


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover_payload_files(input_path: str | Path, pattern: str = "*.json") -> list[Path]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"input path not found: {path}")
    if path.is_file():
        return [path]
    if path.is_dir():
        files = sorted(p for p in path.glob(pattern) if p.is_file())
        if not files:
            raise ValueError(f"no files matched pattern '{pattern}' in directory: {path}")
        return files
    raise ValueError(f"unsupported input path type: {path}")


def load_payload_documents(file_path: str | Path) -> list[tuple[str, IngestPayload]]:
    path = Path(file_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    docs: list[tuple[str, IngestPayload]] = []

    if isinstance(data, dict):
        docs.append((str(path), IngestPayload.model_validate(data)))
        return docs

    if isinstance(data, list):
        for idx, item in enumerate(data, start=1):
            source = f"{path}#{idx}"
            docs.append((source, IngestPayload.model_validate(item)))
        return docs

    raise ValueError(f"invalid payload shape for {path}: expected object or array")


def build_summary(
    payload_documents: list[tuple[str, IngestPayload]],
    repo: Any,
    *,
    input_path: str,
) -> dict[str, Any]:
    started_at = utc_now_iso()
    review_before = repo.count_review_queue() if hasattr(repo, "count_review_queue") else 0

    total = 0
    success = 0
    fail = 0
    run_results: list[dict[str, Any]] = []

    for source, payload in payload_documents:
        total += len(payload.records)
        result = ingest_payload(payload, repo)
        success += int(result.processed_count)
        fail += int(result.error_count)
        run_results.append(
            {
                "source": source,
                "run_id": result.run_id,
                "status": result.status,
                "processed_count": result.processed_count,
                "error_count": result.error_count,
                "record_count": len(payload.records),
            }
        )

    review_after = repo.count_review_queue() if hasattr(repo, "count_review_queue") else review_before
    finished_at = utc_now_iso()

    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "input_path": input_path,
        "payload_count": len(payload_documents),
        "run_count": len(run_results),
        "total": total,
        "success": success,
        "fail": fail,
        "review_queue_count": max(0, review_after - review_before),
        "review_queue_total_before": review_before,
        "review_queue_total_after": review_after,
        "runs": run_results,
    }


def run_bootstrap_ingest(
    *,
    input_path: str,
    pattern: str = "*.json",
) -> dict[str, Any]:
    files = discover_payload_files(input_path, pattern=pattern)
    payload_documents: list[tuple[str, IngestPayload]] = []
    for file_path in files:
        payload_documents.extend(load_payload_documents(file_path))

    with get_connection() as conn:
        repo = PostgresRepository(conn)
        return build_summary(payload_documents, repo, input_path=input_path)


def write_summary_report(summary: dict[str, Any], report_path: str | Path) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch bootstrap ingest runner")
    parser.add_argument("--input", required=True, help="JSON file path or directory path")
    parser.add_argument("--pattern", default="*.json", help="Glob pattern when --input is a directory")
    parser.add_argument("--report", required=True, help="Output report json path")
    args = parser.parse_args()

    summary = run_bootstrap_ingest(input_path=args.input, pattern=args.pattern)
    report_path = write_summary_report(summary, args.report)
    print(json.dumps({"report_path": str(report_path), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
