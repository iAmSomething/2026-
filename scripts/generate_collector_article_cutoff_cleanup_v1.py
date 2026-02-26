from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    has_article_source,
    parse_datetime_like,
    published_at_cutoff_reason,
)

DEFAULT_INPUT = "data/sample_ingest.json"
DEFAULT_FILTERED_OUTPUT = "data/sample_ingest_article_cutoff_filtered.json"
DEFAULT_REPORT_OUTPUT = "data/collector_article_cutoff_cleanup_v1_report.json"


def build_backfill_cleanup_sql(cutoff_iso: str = ARTICLE_PUBLISHED_AT_CUTOFF_ISO) -> dict[str, str]:
    where_clause = (
        "((o.source_channel = 'article') OR COALESCE('article' = ANY(o.source_channels), FALSE)) "
        "AND (a.published_at IS NULL OR a.published_at < %(cutoff)s::timestamptz)"
    )
    return {
        "count_violation_rows": (
            "SELECT COUNT(*)::int AS violation_count "
            "FROM poll_observations o LEFT JOIN articles a ON a.id = o.article_id "
            f"WHERE {where_clause};"
        ),
        "delete_poll_observations": (
            "WITH target AS ("
            "SELECT o.id FROM poll_observations o "
            "LEFT JOIN articles a ON a.id = o.article_id "
            f"WHERE {where_clause}"
            ") "
            "DELETE FROM poll_observations o USING target t "
            "WHERE o.id = t.id;"
        ),
        "delete_orphan_articles": (
            "DELETE FROM articles a "
            "WHERE (a.published_at IS NULL OR a.published_at < %(cutoff)s::timestamptz) "
            "AND NOT EXISTS (SELECT 1 FROM poll_observations o WHERE o.article_id = a.id);"
        ),
        "cleanup_candidates_article_published_at": (
            "UPDATE candidates "
            "SET article_published_at = NULL, updated_at = NOW() "
            "WHERE article_published_at < %(cutoff)s::timestamptz;"
        ),
        "sql_params_example": json.dumps({"cutoff": cutoff_iso}, ensure_ascii=False),
    }


def _is_record_allowed(record: dict[str, Any]) -> tuple[bool, str]:
    observation = record.get("observation") or {}
    article = record.get("article") or {}
    if not has_article_source(
        source_channel=observation.get("source_channel"),
        source_channels=observation.get("source_channels"),
    ):
        return True, "PASS"
    reason = published_at_cutoff_reason(article.get("published_at"))
    return reason == "PASS", reason


def apply_article_cutoff(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        allowed, reason = _is_record_allowed(record)
        if allowed:
            kept.append(record)
            continue
        parsed_published_at = parse_datetime_like((record.get("article") or {}).get("published_at"))
        rejected.append(
            {
                "observation_key": (record.get("observation") or {}).get("observation_key"),
                "source_channel": (record.get("observation") or {}).get("source_channel"),
                "source_channels": (record.get("observation") or {}).get("source_channels"),
                "published_at": (record.get("article") or {}).get("published_at"),
                "published_at_kst": (
                    parsed_published_at.isoformat(timespec="seconds")
                    if parsed_published_at is not None
                    else None
                ),
                "reason": reason,
            }
        )
    return kept, rejected


def generate_cleanup_outputs(
    *,
    input_path: str = DEFAULT_INPUT,
    filtered_output_path: str = DEFAULT_FILTERED_OUTPUT,
    report_output_path: str = DEFAULT_REPORT_OUTPUT,
) -> dict[str, Any]:
    raw_payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    records = raw_payload.get("records") or []
    kept_records, rejected_records = apply_article_cutoff(records)

    filtered_payload = dict(raw_payload)
    filtered_payload["records"] = kept_records
    Path(filtered_output_path).write_text(
        json.dumps(filtered_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "policy": {
            "published_at_cutoff_kst": ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
            "applies_to_source_channel": "article",
        },
        "counts": {
            "input_record_count": len(records),
            "kept_record_count": len(kept_records),
            "cutoff_violation_count": len(rejected_records),
        },
        "cutoff_violation_preview": rejected_records[:20],
        "acceptance_checks": {
            "filtered_payload_has_no_cutoff_violation": len(rejected_records) == 0,
        },
        "backfill_cleanup_sql": build_backfill_cleanup_sql(ARTICLE_PUBLISHED_AT_CUTOFF_ISO),
        "output_paths": {
            "input": input_path,
            "filtered_payload": filtered_output_path,
            "report": report_output_path,
        },
    }
    Path(report_output_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate article cutoff cleanup report and filtered payload")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input ingest payload path")
    parser.add_argument("--filtered-output", default=DEFAULT_FILTERED_OUTPUT, help="Filtered payload output path")
    parser.add_argument("--report-output", default=DEFAULT_REPORT_OUTPUT, help="Cleanup report output path")
    args = parser.parse_args()

    report = generate_cleanup_outputs(
        input_path=args.input,
        filtered_output_path=args.filtered_output,
        report_output_path=args.report_output,
    )
    print(
        json.dumps(
            {
                "counts": report["counts"],
                "acceptance_checks": report["acceptance_checks"],
                "report": args.report_output,
                "filtered_payload": args.filtered_output,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
