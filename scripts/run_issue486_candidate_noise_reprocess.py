#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.services.candidate_token_policy import is_noise_candidate_token

DEFAULT_INPUT = "data/collector_live_news_v1_payload.json"
DEFAULT_KEYSET_OUTPUT = "data/issue486_candidate_noise_keys.json"
DEFAULT_OUTPUT = "data/issue486_candidate_noise_reprocess_report.json"
DEFAULT_REPROCESS_PAYLOAD_OUTPUT = "data/issue486_candidate_noise_reprocess_payload.json"
DEFAULT_REGION_CODE = "11-000"
DEFAULT_OFFICE_TYPE = "광역자치단체장"


def _is_target_record(record: dict[str, Any], *, region_code: str, office_type: str) -> bool:
    observation = record.get("observation") or {}
    return (
        str(observation.get("region_code") or "").strip() == region_code
        and str(observation.get("office_type") or "").strip() == office_type
    )


def _is_candidate_option(option: dict[str, Any]) -> bool:
    option_type = str(option.get("option_type") or "").strip()
    return option_type in {"candidate", "candidate_matchup"}


def _option_name(option: dict[str, Any]) -> str:
    return str(option.get("option_name") or "").strip()


def _observation_key(record: dict[str, Any]) -> str:
    observation = record.get("observation") or {}
    return str(observation.get("observation_key") or "").strip()


def run_reprocess(
    *,
    input_payload_path: Path,
    keyset_output_path: Path,
    output_path: Path,
    reprocess_payload_output_path: Path,
    region_code: str = DEFAULT_REGION_CODE,
    office_type: str = DEFAULT_OFFICE_TYPE,
) -> dict[str, Any]:
    payload = json.loads(input_payload_path.read_text(encoding="utf-8"))
    records = payload.get("records") or []

    target_records = [row for row in records if _is_target_record(row, region_code=region_code, office_type=office_type)]
    keyset: list[str] = []
    items: list[dict[str, Any]] = []
    cleaned_records: list[dict[str, Any]] = []
    total_removed_noise_option_count = 0

    for row in target_records:
        options = row.get("options") or []
        before_candidate_options = [_option_name(opt) for opt in options if _is_candidate_option(opt)]
        removed_noise_tokens: list[str] = []
        cleaned_options: list[dict[str, Any]] = []

        for opt in options:
            option_name = _option_name(opt)
            if _is_candidate_option(opt) and is_noise_candidate_token(option_name):
                removed_noise_tokens.append(option_name or "unknown")
                continue
            cleaned_options.append(opt)

        if not removed_noise_tokens:
            continue

        cleaned_row = deepcopy(row)
        cleaned_row["options"] = cleaned_options
        cleaned_records.append(cleaned_row)

        observation_key = _observation_key(row)
        if observation_key:
            keyset.append(observation_key)
        after_candidate_options = [_option_name(opt) for opt in cleaned_options if _is_candidate_option(opt)]
        total_removed_noise_option_count += len(removed_noise_tokens)

        items.append(
            {
                "observation_key": observation_key,
                "article_url": str((row.get("article") or {}).get("url") or ""),
                "article_title": str((row.get("article") or {}).get("title") or ""),
                "before_candidate_options": before_candidate_options,
                "after_candidate_options": after_candidate_options,
                "removed_noise_tokens": removed_noise_tokens,
                "before_option_count": len(options),
                "after_option_count": len(cleaned_options),
            }
        )

    # Preserve order while removing duplicates.
    dedup_keyset = list(dict.fromkeys(x for x in keyset if x))
    keyset_output_path.write_text(json.dumps(dedup_keyset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    reprocess_payload: dict[str, Any] = {}
    for field in ("run_type", "extractor_version", "llm_model"):
        if field in payload:
            reprocess_payload[field] = payload[field]
    reprocess_payload["records"] = cleaned_records
    reprocess_payload_output_path.write_text(
        json.dumps(reprocess_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    all_after_candidate_human_names = True
    for item in items:
        for option_name in item["after_candidate_options"]:
            if is_noise_candidate_token(option_name):
                all_after_candidate_human_names = False
                break

    report = {
        "issue": 486,
        "target_filters": {
            "region_code": region_code,
            "office_type": office_type,
        },
        "input_payload_path": str(input_payload_path),
        "keyset_output_path": str(keyset_output_path),
        "reprocess_payload_output_path": str(reprocess_payload_output_path),
        "total_input_record_count": len(records),
        "target_record_count": len(target_records),
        "noise_record_count": len(items),
        "total_removed_noise_option_count": total_removed_noise_option_count,
        "acceptance_checks": {
            "target_keyset_extracted": len(dedup_keyset) > 0,
            "seoul_mayor_candidate_only_names": all_after_candidate_human_names,
            "noise_reingest_block_ready": total_removed_noise_option_count > 0,
        },
        "review_queue_candidates": [
            {
                "entity_type": "poll_observation",
                "entity_id": item["observation_key"],
                "issue_type": "candidate_name_noise",
                "review_note": "candidate noise token filtered and skipped: "
                + ", ".join(item["removed_noise_tokens"]),
            }
            for item in items
            if item["observation_key"]
        ],
        "items": items,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue #486 candidate noise reprocess helper")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--keyset-output", default=DEFAULT_KEYSET_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--reprocess-payload-output", default=DEFAULT_REPROCESS_PAYLOAD_OUTPUT)
    parser.add_argument("--region-code", default=DEFAULT_REGION_CODE)
    parser.add_argument("--office-type", default=DEFAULT_OFFICE_TYPE)
    args = parser.parse_args()

    report = run_reprocess(
        input_payload_path=Path(args.input),
        keyset_output_path=Path(args.keyset_output),
        output_path=Path(args.output),
        reprocess_payload_output_path=Path(args.reprocess_payload_output),
        region_code=args.region_code,
        office_type=args.office_type,
    )
    print(f"written: {args.output}")
    print(f"noise_record_count={report['noise_record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
