from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ingest_input_normalization import normalize_option_type
from app.services.ingest_service import _repair_candidate_matchup_scenarios
from app.services.normalization import normalize_percentage

INPUT_PAYLOAD = "data/collector_live_coverage_v2_payload.json"
OUT_BEFORE = "data/issue339_scenario_mix_before.json"
OUT_AFTER = "data/issue339_scenario_mix_after.json"
OUT_REINGEST = "data/issue339_scenario_mix_reingest_payload.json"
OUT_REPORT = "data/issue339_scenario_mix_report.json"
OUT_RUNTIME_CAPTURE = "data/issue339_runtime_after_capture_live.json"
OUT_RUNTIME_REPORT = "data/issue339_runtime_acceptance_live.json"
DEFAULT_RUNTIME_API_URL = (
    "https://2026-api-production.up.railway.app/api/v1/matchups/"
    "2026_local%7C%EA%B8%B0%EC%B4%88%EC%9E%90%EC%B9%98%EB%8B%A8%EC%B2%B4%EC%9E%A5%7C26-710"
)
REQUIRED_SCENARIO_OPTION_SETS = {
    "h2h-전재수-박형준": {"전재수", "박형준"},
    "h2h-전재수-김도읍": {"전재수", "김도읍"},
    "multi-전재수": {"전재수", "박형준", "김도읍", "조경태", "조국", "박재호", "이재성", "윤택근"},
}


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue #339 시나리오 분리 재처리/운영 수용판정 도구")
    parser.add_argument(
        "--runtime-check",
        action="store_true",
        help="운영 matchup API 캡처를 기준으로 #339 수용기준을 판정한다.",
    )
    parser.add_argument("--api-url", default=DEFAULT_RUNTIME_API_URL, help="운영 matchup API URL")
    parser.add_argument(
        "--capture-input",
        default=None,
        help="기존 캡처 JSON 경로(지정 시 API 호출 없이 해당 파일로 판정).",
    )
    parser.add_argument(
        "--capture-output",
        default=OUT_RUNTIME_CAPTURE,
        help="runtime 캡처 저장 경로",
    )
    parser.add_argument(
        "--runtime-report-output",
        default=OUT_RUNTIME_REPORT,
        help="runtime 수용판정 리포트 저장 경로",
    )
    return parser.parse_args()


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


def _extract_matchup_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = raw.get("payload")
    if isinstance(payload, dict):
        return payload
    return raw


def _fetch_runtime_payload(api_url: str) -> dict[str, Any]:
    try:
        with urlrequest.urlopen(api_url, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urlerror.URLError as exc:
        raise RuntimeError(f"runtime API fetch failed: {exc}") from exc
    return json.loads(body)


def evaluate_runtime_acceptance(matchup_payload: dict[str, Any]) -> dict[str, Any]:
    scenarios = list(matchup_payload.get("scenarios") or [])
    scenario_index: dict[str, dict[str, Any]] = {}
    scenario_summaries: list[dict[str, Any]] = []

    for scenario in scenarios:
        key = str(scenario.get("scenario_key") or "default")
        options = list(scenario.get("options") or [])
        value_present_by_option: dict[str, bool] = {}
        option_names: list[str] = []
        for opt in options:
            name = str(opt.get("option_name") or "").strip()
            if not name:
                continue
            option_names.append(name)
            normalized = normalize_percentage(opt.get("value_raw"))
            has_value = isinstance(opt.get("value_mid"), (int, float)) or (normalized.value_mid is not None)
            value_present_by_option[name] = value_present_by_option.get(name, False) or has_value
        deduped_option_names = sorted(set(option_names))
        scenario_index[key] = {
            "scenario_key": key,
            "scenario_type": scenario.get("scenario_type"),
            "scenario_title": scenario.get("scenario_title"),
            "option_names": deduped_option_names,
            "value_present_by_option": value_present_by_option,
        }
        scenario_summaries.append(
            {
                "scenario_key": key,
                "scenario_type": scenario.get("scenario_type"),
                "scenario_title": scenario.get("scenario_title"),
                "option_names": deduped_option_names,
            }
        )

    required_three_blocks_detail: dict[str, dict[str, Any]] = {}
    for key, expected_names in REQUIRED_SCENARIO_OPTION_SETS.items():
        entry = scenario_index.get(key)
        if not entry:
            required_three_blocks_detail[key] = {
                "present": False,
                "expected_option_names": sorted(expected_names),
                "observed_option_names": [],
                "option_set_match": False,
                "all_values_present": False,
            }
            continue
        observed_names = set(entry["option_names"])
        required_three_blocks_detail[key] = {
            "present": True,
            "expected_option_names": sorted(expected_names),
            "observed_option_names": sorted(observed_names),
            "option_set_match": observed_names == expected_names,
            "all_values_present": all(entry["value_present_by_option"].get(name, False) for name in expected_names),
        }

    scenario_count_ge_3 = len(scenarios) >= 3
    has_required_three_blocks = all(detail["present"] for detail in required_three_blocks_detail.values())
    block_option_mixing_zero = has_required_three_blocks and all(
        detail["option_set_match"] for detail in required_three_blocks_detail.values()
    )
    required_block_values_present = has_required_three_blocks and all(
        detail["all_values_present"] for detail in required_three_blocks_detail.values()
    )
    default_removed = "default" not in scenario_index
    acceptance_pass = (
        scenario_count_ge_3
        and has_required_three_blocks
        and block_option_mixing_zero
        and required_block_values_present
        and default_removed
    )

    return {
        "issue": 339,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "matchup_id": matchup_payload.get("matchup_id"),
        "region_code": matchup_payload.get("region_code"),
        "office_type": matchup_payload.get("office_type"),
        "scenario_count": len(scenarios),
        "scenario_keys": sorted(scenario_index.keys()),
        "scenario_summaries": scenario_summaries,
        "required_three_blocks_detail": required_three_blocks_detail,
        "acceptance_checks": {
            "scenario_count_ge_3": scenario_count_ge_3,
            "has_required_three_blocks": has_required_three_blocks,
            "block_option_mixing_zero": block_option_mixing_zero,
            "required_block_values_present": required_block_values_present,
            "default_removed": default_removed,
            "acceptance_pass": acceptance_pass,
        },
    }


def run_runtime_acceptance(
    *,
    api_url: str = DEFAULT_RUNTIME_API_URL,
    capture_input_path: str | None = None,
    capture_output_path: str = OUT_RUNTIME_CAPTURE,
    report_output_path: str = OUT_RUNTIME_REPORT,
) -> dict[str, Any]:
    if capture_input_path:
        raw_capture = _parse_json(capture_input_path)
        matchup_payload = _extract_matchup_payload(raw_capture)
        captured_at = str(raw_capture.get("captured_at") or datetime.now(timezone.utc).isoformat())
        capture_url = str(raw_capture.get("url") or api_url)
    else:
        matchup_payload = _fetch_runtime_payload(api_url)
        captured_at = datetime.now(timezone.utc).isoformat()
        capture_url = api_url

    runtime_capture = {
        "url": capture_url,
        "captured_at": captured_at,
        "payload": matchup_payload,
    }
    _write_json(capture_output_path, runtime_capture)

    report = evaluate_runtime_acceptance(matchup_payload)
    report["capture"] = {
        "url": capture_url,
        "captured_at": captured_at,
        "capture_output_path": capture_output_path,
    }
    _write_json(report_output_path, report)
    return report


def main() -> None:
    args = _parse_args()
    if args.runtime_check:
        report = run_runtime_acceptance(
            api_url=args.api_url,
            capture_input_path=args.capture_input,
            capture_output_path=args.capture_output,
            report_output_path=args.runtime_report_output,
        )
    else:
        report = run_reprocess()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
