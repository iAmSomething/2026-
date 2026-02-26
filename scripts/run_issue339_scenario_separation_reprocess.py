from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.services.ingest_input_normalization import normalize_option_type
from app.services.ingest_service import _repair_candidate_matchup_scenarios
from app.services.normalization import normalize_percentage

INPUT_PAYLOAD = "data/collector_live_coverage_v2_payload.json"
OUT_BEFORE = "data/issue339_scenario_mix_before.json"
OUT_AFTER = "data/issue339_scenario_mix_after.json"
OUT_REINGEST = "data/issue339_scenario_mix_reingest_payload.json"
OUT_REPORT = "data/issue339_scenario_mix_report.json"


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_option_payload(option: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(option)
    row["option_type"] = normalize_option_type(row.get("option_type"), row.get("option_name"))[0]
    if row["value_mid"] is None if "value_mid" in row else True:
        normalized = normalize_percentage(row.get("value_raw"))
        row["value_min"] = normalized.value_min
        row["value_max"] = normalized.value_max
        row["value_mid"] = normalized.value_mid
        row["is_missing"] = normalized.is_missing
    row["scenario_key"] = (str(row.get("scenario_key") or "").strip() or "default")
    if "scenario_type" not in row:
        row["scenario_type"] = None
    if "scenario_title" not in row:
        row["scenario_title"] = None
    return row


def _target_record(record: dict[str, Any]) -> bool:
    obs = record.get("observation") or {}
    options = record.get("options") or []
    if str(obs.get("region_code") or "") != "26-710":
        return False
    survey = str(obs.get("survey_name") or "")
    if "다자대결" in survey:
        return True
    candidate_names = [str(x.get("option_name") or "") for x in options if x.get("option_type") == "candidate_matchup"]
    return len(candidate_names) != len(set(candidate_names))


def run_reprocess() -> dict[str, Any]:
    source = _parse_json(INPUT_PAYLOAD)
    records = list(source.get("records") or [])

    before_rows: list[dict[str, Any]] = []
    after_rows: list[dict[str, Any]] = []
    reprocessed_records: list[dict[str, Any]] = []
    target_count = 0
    changed_count = 0

    for record in records:
        out_record = deepcopy(record)
        if not _target_record(record):
            reprocessed_records.append(out_record)
            continue

        target_count += 1
        obs = record.get("observation") or {}
        before_options = [deepcopy(opt) for opt in (record.get("options") or [])]
        normalized_options = [_normalize_option_payload(opt) for opt in (record.get("options") or [])]
        changed = _repair_candidate_matchup_scenarios(
            survey_name=obs.get("survey_name"),
            options=normalized_options,
        )
        if changed:
            changed_count += 1
        after_options = [deepcopy(opt) for opt in normalized_options]

        out_record["options"] = after_options
        reprocessed_records.append(out_record)
        before_rows.append(
            {
                "observation_key": obs.get("observation_key"),
                "region_code": obs.get("region_code"),
                "survey_name": obs.get("survey_name"),
                "options": before_options,
            }
        )
        after_rows.append(
            {
                "observation_key": obs.get("observation_key"),
                "region_code": obs.get("region_code"),
                "survey_name": obs.get("survey_name"),
                "options": after_options,
            }
        )

    reingest_payload = {
        "run_type": "collector_issue339_scenario_reprocess_v1",
        "extractor_version": "collector-issue339-scenario-reprocess-v1",
        "llm_model": None,
        "records": reprocessed_records,
    }

    scenario_counts: dict[str, int] = {}
    candidate_name_before: set[str] = set()
    candidate_name_after: set[str] = set()
    for row in before_rows:
        for opt in row.get("options") or []:
            if opt.get("option_type") != "candidate_matchup":
                continue
            candidate_name_before.add(str(opt.get("option_name") or ""))
    for row in after_rows:
        for opt in row.get("options") or []:
            if opt.get("option_type") != "candidate_matchup":
                continue
            candidate_name_after.add(str(opt.get("option_name") or ""))
            key = str(opt.get("scenario_key") or "default")
            scenario_counts[key] = scenario_counts.get(key, 0) + 1

    required_three_blocks = {
        "h2h_전재수_박형준": "h2h-전재수-박형준" in scenario_counts,
        "h2h_전재수_김도읍": "h2h-전재수-김도읍" in scenario_counts,
        "multi_전재수": "multi-전재수" in scenario_counts,
    }

    scenario_count_ge_3 = len(scenario_counts) >= 3
    has_required_three_blocks = all(required_three_blocks.values())

    report = {
        "issue": 339,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "source_payload": INPUT_PAYLOAD,
        "target_record_count": target_count,
        "changed_record_count": changed_count,
        "scenario_option_counts_after": scenario_counts,
        "candidate_mapping_loss": {
            "before_candidate_names": sorted(candidate_name_before),
            "after_candidate_names": sorted(candidate_name_after),
            "lost_names": sorted(candidate_name_before - candidate_name_after),
            "added_names": sorted(candidate_name_after - candidate_name_before),
            "loss_detected": len(candidate_name_before - candidate_name_after) > 0,
        },
        "acceptance_checks": {
            "target_records_changed": target_count == changed_count and target_count > 0,
            "target_records_ready_or_changed": (
                (target_count == changed_count and target_count > 0)
                or (target_count > 0 and scenario_count_ge_3 and has_required_three_blocks)
            ),
            "scenario_count_ge_3": scenario_count_ge_3,
            "has_required_three_blocks": has_required_three_blocks,
            "required_three_blocks_detail": required_three_blocks,
            "candidate_mapping_not_lost": len(candidate_name_before - candidate_name_after) == 0,
        },
        "artifacts": {
            "before_path": OUT_BEFORE,
            "after_path": OUT_AFTER,
            "reingest_payload_path": OUT_REINGEST,
        },
    }

    _write_json(OUT_BEFORE, {"records": before_rows})
    _write_json(OUT_AFTER, {"records": after_rows})
    _write_json(OUT_REINGEST, reingest_payload)
    _write_json(OUT_REPORT, report)
    return report


def main() -> None:
    report = run_reprocess()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
