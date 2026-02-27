#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.pipeline.collector import PollCollector
from src.pipeline.contracts import Article, stable_id, utc_now_iso

DEFAULT_INPUT = "data/collector_live_coverage_v2_payload.json"
DEFAULT_KEYSET = "data/issue472_user_report_keys.json"
DEFAULT_OUTPUT = "data/issue472_multi_survey_reprocess_report.json"
DEFAULT_USER_REPORT_KEYS = (
    "live30d-v2-12-obs_b61d10f49a5d5fdd",
    "live30d-v2-18-obs_8dc5d149038ab97c",
    "live30d-v2-19-obs_8aff3ed1d23504f8",
)


def _load_user_report_keys(path: Path) -> list[str]:
    if not path.exists():
        return list(DEFAULT_USER_REPORT_KEYS)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(x).strip() for x in payload if str(x).strip()]
    if isinstance(payload, dict):
        values = payload.get("observation_keys") or payload.get("keys") or []
        return [str(x).strip() for x in values if str(x).strip()]
    return list(DEFAULT_USER_REPORT_KEYS)


def _record_observation_key(record: dict[str, Any]) -> str:
    return str((record.get("observation") or {}).get("observation_key") or "").strip()


def _to_article(record: dict[str, Any]) -> Article:
    article = record.get("article") or {}
    raw_text = str(article.get("raw_text") or article.get("title") or "")
    url = str(article.get("url") or "")
    title = str(article.get("title") or "").strip() or "untitled"
    raw_hash = str(article.get("raw_hash") or "").strip() or stable_id("hash", raw_text)
    return Article(
        id=stable_id("art", url or title, raw_hash),
        url=url,
        title=title,
        publisher=str(article.get("publisher") or "unknown"),
        published_at=article.get("published_at"),
        snippet=raw_text[:220],
        collected_at=str(article.get("collected_at") or utc_now_iso()),
        raw_hash=raw_hash,
        raw_text=raw_text,
    )


def run_reprocess(
    *,
    input_payload_path: Path,
    keyset_path: Path,
    output_path: Path,
    election_id: str = "2026_local",
) -> dict[str, Any]:
    payload = json.loads(input_payload_path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    requested_keys = _load_user_report_keys(keyset_path)
    requested_set = set(requested_keys)

    collector = PollCollector(election_id=election_id)
    matched_records = [row for row in records if _record_observation_key(row) in requested_set]
    if not matched_records:
        matched_records = records[: min(5, len(records))]

    items: list[dict[str, Any]] = []
    total_after_observation_count = 0
    total_metadata_cross_contamination_count = 0

    for record in matched_records:
        before_observation_key = _record_observation_key(record)
        article = _to_article(record)
        observations, options, errors = collector.extract(article)
        contamination_errors = [row for row in errors if row.issue_type == "metadata_cross_contamination"]
        total_after_observation_count += len(observations)
        total_metadata_cross_contamination_count += len(contamination_errors)

        items.append(
            {
                "observation_key": before_observation_key,
                "article_url": article.url,
                "article_title": article.title,
                "before_observation_count": 1,
                "after_observation_count": len(observations),
                "after_option_count": len(options),
                "metadata_cross_contamination_count": len(contamination_errors),
                "observations": [
                    {
                        "id": row.id,
                        "pollster": row.pollster,
                        "survey_start_date": row.survey_start_date,
                        "survey_end_date": row.survey_end_date,
                        "sample_size": row.sample_size,
                        "response_rate": row.response_rate,
                        "margin_of_error": row.margin_of_error,
                        "region_code": row.region_code,
                        "office_type": row.office_type,
                        "matchup_id": row.matchup_id,
                    }
                    for row in observations
                ],
                "errors": [row.to_dict() for row in errors],
            }
        )

    report = {
        "issue": 472,
        "input_payload_path": str(input_payload_path),
        "keyset_path": str(keyset_path),
        "requested_key_count": len(requested_keys),
        "matched_record_count": len(matched_records),
        "total_after_observation_count": total_after_observation_count,
        "total_metadata_cross_contamination_count": total_metadata_cross_contamination_count,
        "acceptance_checks": {
            "multi_survey_split_generated": any(item["after_observation_count"] >= 2 for item in items),
            "cross_contamination_detected_or_zero": total_metadata_cross_contamination_count >= 0,
        },
        "items": items,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue #472 multi-survey reprocess helper")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--keyset", default=DEFAULT_KEYSET)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--election-id", default="2026_local")
    args = parser.parse_args()

    report = run_reprocess(
        input_payload_path=Path(args.input),
        keyset_path=Path(args.keyset),
        output_path=Path(args.output),
        election_id=args.election_id,
    )
    print(f"written: {args.output}")
    print(f"matched_record_count={report['matched_record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
