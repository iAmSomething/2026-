#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.ingest_service import (
    _apply_article_scope_hint_fallback,
    _apply_scope_region_conflict_resolution,
    _apply_survey_name_matchup_correction,
    _resolve_observation_scope,
    _sync_region_payload_from_observation,
)

DEFAULT_INPUT = Path("data/collector_live_news_v1_payload.json")
DEFAULT_OUTPUT_PAYLOAD = Path("data/issue504_scope_classifier_v3_reprocess_payload.json")
DEFAULT_OUTPUT_DIFF = Path("data/issue504_scope_classifier_v3_before_after.json")
DEFAULT_OUTPUT_REPORT = Path("data/issue504_scope_classifier_v3_quarantine_report.json")
TARGET_LEAK_REGION_CODES = {"26-710", "28-450", "48-110"}
TARGET_METRO_REGION_CODES = {"26-000", "28-000", "48-000"}
REGIONAL_OFFICE_TYPES = {"광역자치단체장", "교육감", "광역의회"}
LOCAL_OFFICE_TYPES = {"기초자치단체장", "기초의회"}


def _snapshot(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_key": observation.get("observation_key"),
        "survey_name": observation.get("survey_name"),
        "region_code": observation.get("region_code"),
        "office_type": observation.get("office_type"),
        "matchup_id": observation.get("matchup_id"),
        "audience_scope": observation.get("audience_scope"),
        "audience_region_code": observation.get("audience_region_code"),
    }


def _apply_classifier(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    article = record.get("article") or {}
    observation = dict(record.get("observation") or {})
    region_payload = record.get("region")
    region_payload = dict(region_payload) if isinstance(region_payload, dict) else None
    before = _snapshot(observation)

    question_signal_applied = _apply_survey_name_matchup_correction(observation_payload=observation, article_title=None)
    scope_resolution = _resolve_observation_scope(
        observation,
        prefer_declared_scope=question_signal_applied,
    )
    observation["audience_scope"] = scope_resolution.scope
    observation["audience_region_code"] = scope_resolution.audience_region_code
    conflict_resolution_applied = _apply_scope_region_conflict_resolution(
        observation_payload=observation,
        inferred_region_code=scope_resolution.inferred_region_code,
    )

    title_fallback_applied = False
    title_keyword = None
    if not question_signal_applied and scope_resolution.inferred_region_code is None:
        title_fallback_applied, title_keyword = _apply_article_scope_hint_fallback(
            observation_payload=observation,
            region_payload=region_payload,
            article_title=str(article.get("title") or ""),
            article_raw_text=str(article.get("raw_text") or ""),
        )
    region_payload = _sync_region_payload_from_observation(region_payload=region_payload, observation_payload=observation)
    after = _snapshot(observation)
    trace = {
        "question_signal_applied": question_signal_applied,
        "inferred_scope": scope_resolution.inferred_scope,
        "inferred_region_code": scope_resolution.inferred_region_code,
        "confidence": scope_resolution.confidence,
        "hard_fail_reason": scope_resolution.hard_fail_reason,
        "low_confidence_reason": scope_resolution.low_confidence_reason,
        "conflict_resolution_applied": conflict_resolution_applied,
        "title_body_fallback_applied": title_fallback_applied,
        "title_body_keyword": title_keyword,
    }
    return before, after, region_payload, trace


def _is_quarantine_target(after: dict[str, Any], trace: dict[str, Any]) -> tuple[bool, str | None]:
    office_type = str(after.get("office_type") or "")
    region_code = str(after.get("region_code") or "")
    if trace.get("hard_fail_reason"):
        return True, "SCOPE_HARD_FAIL"
    if office_type in REGIONAL_OFFICE_TYPES and region_code and not region_code.endswith("-000"):
        return True, "REGIONAL_OFFICE_WITH_LOCAL_REGION"
    if office_type in LOCAL_OFFICE_TYPES and region_code.endswith("-000"):
        return True, "LOCAL_OFFICE_WITH_SIDO_REGION"
    return False, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build scope-classifier-v3 reprocess/quarantine bundle for issue #504")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-payload", default=str(DEFAULT_OUTPUT_PAYLOAD))
    parser.add_argument("--output-diff", default=str(DEFAULT_OUTPUT_DIFF))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_payload = Path(args.output_payload)
    output_diff = Path(args.output_diff)
    output_report = Path(args.output_report)

    source = json.loads(input_path.read_text(encoding="utf-8"))
    records = source.get("records")
    if not isinstance(records, list):
        records = []

    selected_records: list[dict[str, Any]] = []
    before_after: list[dict[str, Any]] = []
    quarantine_records: list[dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        before, after, region_payload, trace = _apply_classifier(record)
        changed = before != after
        target_related = (
            str(before.get("region_code") or "") in TARGET_LEAK_REGION_CODES
            or str(after.get("region_code") or "") in TARGET_METRO_REGION_CODES
        )
        if changed and target_related:
            next_record = dict(record)
            next_record["observation"] = dict(record.get("observation") or {})
            for key, value in after.items():
                if key == "observation_key":
                    continue
                next_record["observation"][key] = value
            if region_payload is not None:
                next_record["region"] = region_payload
            selected_records.append(next_record)

            row = {"before": before, "after": after, "trace": trace}
            before_after.append(row)

            quarantine, reason = _is_quarantine_target(after, trace)
            if quarantine:
                quarantine_records.append(
                    {
                        "observation_key": after.get("observation_key"),
                        "reason_code": reason,
                        "after": after,
                        "trace": trace,
                    }
                )

    payload = {
        "run_type": "manual",
        "extractor_version": "issue504_scope_classifier_v3_reprocess",
        "records": selected_records,
    }
    report = {
        "issue": 504,
        "algorithm_version": "scope_classifier_v3",
        "input_path": str(input_path),
        "target_record_count": len(selected_records),
        "before_after_count": len(before_after),
        "quarantine_count": len(quarantine_records),
        "acceptance_checks": {
            "target_records_found": len(selected_records) > 0,
            "quarantine_zero": len(quarantine_records) == 0,
        },
        "quarantine_records": quarantine_records,
    }

    output_payload.parent.mkdir(parents=True, exist_ok=True)
    output_diff.parent.mkdir(parents=True, exist_ok=True)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_payload.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_diff.write_text(json.dumps(before_after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {output_payload}")
    print(f"written: {output_diff}")
    print(f"written: {output_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
