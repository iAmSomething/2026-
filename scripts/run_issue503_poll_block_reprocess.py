#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.pipeline.collector import CollectorOutput, PollCollector
from src.pipeline.contracts import Article, stable_id, utc_now_iso
from src.pipeline.ingest_adapter import collector_output_to_ingest_payload

DEFAULT_INPUT = "data/collector_live_coverage_v2_payload.json"
DEFAULT_REPORT_OUTPUT = "data/issue503_poll_block_reprocess_report.json"
DEFAULT_BEFORE_AFTER_OUTPUT = "data/issue503_poll_block_before_after.json"
DEFAULT_REINGEST_OUTPUT = "data/issue503_poll_block_reingest_payload.json"
DEFAULT_TARGET_REGION_CODES = ("26-000", "28-450", "26-710")


def _record_observation_key(record: dict[str, Any]) -> str:
    return str((record.get("observation") or {}).get("observation_key") or "").strip()


def _record_region_code(record: dict[str, Any]) -> str:
    observation = record.get("observation") or {}
    return str(observation.get("region_code") or "").strip()


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


def _candidate_options_by_observation(options: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for row in options:
        if getattr(row, "option_type", "") != "candidate":
            continue
        grouped.setdefault(str(getattr(row, "observation_id", "")), []).append(row)
    return grouped


def run_reprocess(
    *,
    input_payload_path: Path,
    report_output_path: Path,
    before_after_output_path: Path,
    reingest_output_path: Path | None = None,
    target_region_codes: tuple[str, ...] = DEFAULT_TARGET_REGION_CODES,
    election_id: str = "2026_local",
) -> dict[str, Any]:
    payload = json.loads(input_payload_path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    target_set = {str(code).strip() for code in target_region_codes if str(code).strip()}

    matched_records = [row for row in records if _record_region_code(row) in target_set]
    if not matched_records:
        matched_records = records[: min(5, len(records))]

    collector = PollCollector(election_id=election_id)
    reingest_output = CollectorOutput()
    before_after_items: list[dict[str, Any]] = []
    dead_letter_count = 0
    metadata_cross_contamination_count = 0
    all_options_bound_to_poll_block = True
    scenario_split_present = False

    for record in matched_records:
        before_observation = record.get("observation") or {}
        before_options = record.get("options") or []

        article = _to_article(record)
        observations, options, errors = collector.extract(article)
        reingest_output.articles.append(article)
        reingest_output.poll_observations.extend(observations)
        reingest_output.poll_options.extend(options)
        reingest_output.review_queue.extend(errors)
        options_by_observation = _candidate_options_by_observation(options)

        observation_rows: list[dict[str, Any]] = []
        for row in observations:
            row_options = options_by_observation.get(row.id, [])
            option_poll_block_ids = sorted({str(getattr(opt, "poll_block_id", "") or "") for opt in row_options})
            if any(value != row.poll_block_id for value in option_poll_block_ids):
                all_options_bound_to_poll_block = False
            observation_rows.append(
                {
                    "id": row.id,
                    "poll_block_id": row.poll_block_id,
                    "pollster": row.pollster,
                    "survey_start_date": row.survey_start_date,
                    "survey_end_date": row.survey_end_date,
                    "sample_size": row.sample_size,
                    "scenario_keys": sorted({str(getattr(opt, "scenario_key", "") or "") for opt in row_options}),
                    "candidate_values": [
                        {
                            "option_name": opt.option_name,
                            "scenario_key": opt.scenario_key,
                            "value_mid": opt.value_mid,
                            "poll_block_id": opt.poll_block_id,
                        }
                        for opt in row_options
                    ],
                }
            )

        dead_letters = [item.to_dict() for item in errors]
        dead_letter_count += len(dead_letters)
        metadata_cross_contamination_count += sum(
            1 for item in dead_letters if str(item.get("issue_type") or "") == "metadata_cross_contamination"
        )
        scenario_keys = {
            key
            for obs in observation_rows
            for key in (obs.get("scenario_keys") or [])
            if isinstance(key, str) and key
        }
        if {
            "h2h-전재수-박형준",
            "h2h-전재수-김도읍",
            "multi-전재수",
        }.issubset(scenario_keys):
            scenario_split_present = True

        before_after_items.append(
            {
                "observation_key": _record_observation_key(record),
                "region_code": _record_region_code(record),
                "article_url": article.url,
                "article_title": article.title,
                "before": {
                    "observation_poll_block_id": before_observation.get("poll_block_id"),
                    "option_count": len(before_options),
                    "option_scenario_keys": sorted(
                        {
                            str((row.get("scenario_key") if isinstance(row, dict) else None) or "default")
                            for row in before_options
                        }
                    ),
                },
                "after": {
                    "observation_count": len(observations),
                    "candidate_option_count": sum(len(rows) for rows in options_by_observation.values()),
                    "poll_block_count": len({row.poll_block_id for row in observations}),
                    "observations": observation_rows,
                },
                "dead_letters": dead_letters,
            }
        )

    before_after = {
        "issue": 503,
        "input_payload_path": str(input_payload_path),
        "target_region_codes": list(target_set),
        "items": before_after_items,
    }
    before_after_output_path.write_text(json.dumps(before_after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    reingest_record_count = 0
    if reingest_output_path is not None:
        ingest_payload = collector_output_to_ingest_payload(reingest_output)
        reingest_record_count = len(ingest_payload.get("records") or [])
        reingest_output_path.write_text(json.dumps(ingest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "issue": 503,
        "input_payload_path": str(input_payload_path),
        "before_after_output_path": str(before_after_output_path),
        "reingest_output_path": str(reingest_output_path) if reingest_output_path is not None else None,
        "reingest_record_count": reingest_record_count,
        "target_region_codes": list(target_set),
        "matched_record_count": len(matched_records),
        "dead_letter_count": dead_letter_count,
        "metadata_cross_contamination_count": metadata_cross_contamination_count,
        "acceptance_checks": {
            "matched_records_present": len(matched_records) > 0,
            "multi_poll_block_split_present": any(
                item.get("after", {}).get("poll_block_count", 0) >= 2 for item in before_after_items
            ),
            "scenario_split_present": scenario_split_present,
            "all_options_bound_to_poll_block": all_options_bound_to_poll_block,
            "metadata_cross_contamination_zero": metadata_cross_contamination_count == 0,
        },
    }
    report_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue #503 poll-block normalization reprocess helper")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--report-output", default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--before-after-output", default=DEFAULT_BEFORE_AFTER_OUTPUT)
    parser.add_argument("--reingest-output", default=DEFAULT_REINGEST_OUTPUT)
    parser.add_argument("--target-region-codes", default=",".join(DEFAULT_TARGET_REGION_CODES))
    parser.add_argument("--election-id", default="2026_local")
    args = parser.parse_args()

    target_codes = tuple(part.strip() for part in str(args.target_region_codes).split(",") if part.strip())
    report = run_reprocess(
        input_payload_path=Path(args.input),
        report_output_path=Path(args.report_output),
        before_after_output_path=Path(args.before_after_output),
        reingest_output_path=Path(args.reingest_output),
        target_region_codes=target_codes,
        election_id=args.election_id,
    )
    print(f"written: {args.report_output}")
    print(f"written: {args.before_after_output}")
    print(f"written: {args.reingest_output}")
    print(f"matched_record_count={report['matched_record_count']}")
    print(f"dead_letter_count={report['dead_letter_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
