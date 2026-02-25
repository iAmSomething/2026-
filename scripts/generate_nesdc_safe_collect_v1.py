from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.pipeline.contracts import new_review_queue_item, normalize_value

KST = ZoneInfo("Asia/Seoul")

INPUT_REGISTRY = "data/nesdc_registry_snapshot_v1.json"
INPUT_ADAPTER = "data/nesdc_pdf_adapter_v2_5pollsters.json"

OUT_DATA = "data/collector_nesdc_safe_collect_v1.json"
OUT_REPORT = "data/collector_nesdc_safe_collect_v1_report.json"
OUT_REVIEW_QUEUE = "data/collector_nesdc_safe_collect_v1_review_queue_candidates.json"

GENERAL_RELEASE_HOURS = 24
PERIODICAL_RELEASE_HOURS = 48


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_kst(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            return dt.astimezone(KST)
        except ValueError:
            continue
    return None


def _release_policy_hours(
    row: dict[str, Any],
    *,
    general_hours: int,
    periodical_hours: int,
) -> int:
    media_type = str(row.get("media_type") or "")
    if "정기간행물" in media_type:
        return periodical_hours
    return general_hours


def _compute_release_at_kst(
    row: dict[str, Any],
    *,
    policy_hours: int,
) -> datetime | None:
    release_at = _parse_kst(row.get("pdf_release_at_kst"))
    if release_at is not None:
        return release_at
    base = _parse_kst(row.get("first_publish_at_kst")) or _parse_kst(row.get("registered_at"))
    if base is None:
        return None
    return base + timedelta(hours=policy_hours)


def _parse_explicit_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def _extract_option_items(adapter_row: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in adapter_row.get("result_items") or []:
        value_raw = item.get("value_raw")
        norm = normalize_value(value_raw)
        items.append(
            {
                "question": item.get("question"),
                "option": item.get("option"),
                "value_raw": value_raw,
                "value_min": norm.value_min,
                "value_max": norm.value_max,
                "value_mid": norm.value_mid,
                "is_missing": norm.is_missing,
                "provenance": item.get("provenance") or {},
            }
        )
    return items


def generate_nesdc_safe_collect_v1(
    *,
    registry_path: str = INPUT_REGISTRY,
    adapter_path: str = INPUT_ADAPTER,
    safe_window_hours: int | None = None,
    general_release_hours: int = GENERAL_RELEASE_HOURS,
    periodical_release_hours: int = PERIODICAL_RELEASE_HOURS,
    as_of_kst: datetime | None = None,
) -> dict[str, Any]:
    registry = _parse_json(registry_path)
    adapter = _parse_json(adapter_path)

    as_of = as_of_kst or datetime.now(tz=KST)
    if safe_window_hours is not None:
        general_release_hours = safe_window_hours
        periodical_release_hours = safe_window_hours

    registry_rows = list(registry.get("records") or [])
    adapter_rows = list(adapter.get("records") or [])
    adapter_map = {str(r.get("ntt_id")): r for r in adapter_rows if r.get("ntt_id") is not None}
    adapter_pollster_map: dict[str, dict[str, Any]] = {}
    for row in adapter_rows:
        pollster = str(row.get("pollster") or "").strip()
        if not pollster or pollster in adapter_pollster_map:
            continue
        if row.get("result_items"):
            adapter_pollster_map[pollster] = row

    output_records: list[dict[str, Any]] = []
    pending_records: list[dict[str, Any]] = []
    review_queue_candidates: list[dict[str, Any]] = []
    eligible_rows: list[tuple[dict[str, Any], int, datetime | None]] = []

    fallback_count = 0
    template_fallback_count = 0
    hard_fallback_count = 0
    eligibility_parse_error_count = 0
    safe_window_guard_block_count = 0
    manual_opt_out_count = 0
    success_count = 0
    exact_success_count = 0
    normalization_ok_option_count = 0
    total_option_count = 0

    pollster_counter: Counter[str] = Counter()

    for row in registry_rows:
        ntt_id = str(row.get("ntt_id") or "")
        pollster = str(row.get("pollster") or "미상조사기관")
        release_policy_hours = _release_policy_hours(
            row,
            general_hours=general_release_hours,
            periodical_hours=periodical_release_hours,
        )
        release_at = _compute_release_at_kst(row, policy_hours=release_policy_hours)
        release_gate_passed = bool(release_at and as_of >= release_at)
        explicit = row.get("auto_collect_eligible_48h")
        parsed_explicit: bool | None = None

        if explicit is not None:
            parsed_explicit = _parse_explicit_bool(explicit)
            if parsed_explicit is None:
                eligibility_parse_error_count += 1
                review_queue_candidates.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=ntt_id or f"invalid-eligibility-{eligibility_parse_error_count}",
                        issue_type="mapping_error",
                        stage="nesdc_safe_collect_v1",
                        error_code="INVALID_AUTO_COLLECT_ELIGIBLE_48H",
                        error_message="unsupported explicit eligibility value; row skipped",
                        source_url=row.get("detail_url"),
                        payload={
                            "ntt_id": ntt_id,
                            "pollster": pollster,
                            "auto_collect_eligible_48h": explicit,
                        },
                    ).to_dict()
                )
                continue
            if parsed_explicit is False:
                manual_opt_out_count += 1

        if parsed_explicit is False:
            continue

        if not release_gate_passed:
            pending_records.append(
                {
                    "ntt_id": ntt_id,
                    "pollster": pollster,
                    "registered_at": row.get("registered_at"),
                    "first_publish_at_kst": row.get("first_publish_at_kst"),
                    "release_policy_hours": release_policy_hours,
                    "release_at_kst": release_at.isoformat(timespec="seconds") if release_at else None,
                    "release_gate_passed": False,
                    "collect_status": "pending_official_release",
                    "source_channel": "nesdc",
                    "detail_url": row.get("detail_url"),
                    "legal_meta": {
                        "survey_datetime": row.get("survey_datetime_text"),
                        "survey_population": row.get("survey_population"),
                        "sample_size": row.get("sample_size"),
                        "response_rate": row.get("response_rate"),
                        "margin_of_error": row.get("margin_of_error_text"),
                        "method": row.get("method"),
                    },
                    "result_options": [],
                    "adapter_mode": "pending_release",
                    "adapter_profile": {"profile_key": "pending_release", "pollster": pollster},
                    "fallback_applied": False,
                }
            )
            if parsed_explicit is True:
                safe_window_guard_block_count += 1
                review_queue_candidates.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=ntt_id or f"safe-window-guard-{safe_window_guard_block_count}",
                        issue_type="mapping_error",
                        stage="nesdc_safe_collect_v1",
                        error_code="SAFE_WINDOW_GUARD_BLOCKED",
                        error_message="explicit eligibility=true blocked by release-at gate",
                        source_url=row.get("detail_url"),
                        payload={
                            "ntt_id": ntt_id,
                            "pollster": pollster,
                            "auto_collect_eligible_48h": explicit,
                            "registered_at": row.get("registered_at"),
                            "release_policy_hours": release_policy_hours,
                            "release_at_kst": release_at.isoformat(timespec="seconds") if release_at else None,
                            "as_of_kst": as_of.isoformat(timespec="seconds"),
                        },
                    ).to_dict()
                )
            continue

        eligible_rows.append((row, release_policy_hours, release_at))

    for row, release_policy_hours, release_at in eligible_rows:
        ntt_id = str(row.get("ntt_id") or "")
        pollster = str(row.get("pollster") or "미상조사기관")
        adapter_row = adapter_map.get(ntt_id)
        adapter_mode = "adapter_exact"
        adapter_profile = {"profile_key": f"ntt:{ntt_id}", "pollster": pollster}
        used_template_fallback = False
        if adapter_row is None:
            adapter_row = adapter_pollster_map.get(pollster)
            if adapter_row is not None:
                adapter_mode = "adapter_pollster_template_fallback"
                adapter_profile = {"profile_key": f"pollster:{pollster}", "pollster": pollster}
                used_template_fallback = True

        record = {
            "ntt_id": ntt_id,
            "pollster": pollster,
            "registered_at": row.get("registered_at"),
            "first_publish_at_kst": row.get("first_publish_at_kst"),
            "release_policy_hours": release_policy_hours,
            "release_at_kst": release_at.isoformat(timespec="seconds") if release_at else None,
            "release_gate_passed": True,
            "collect_status": "collected",
            "safe_window_eligible": True,
            "source_channel": "nesdc",
            "detail_url": row.get("detail_url"),
            "legal_meta": {
                "survey_datetime": row.get("survey_datetime_text"),
                "survey_population": row.get("survey_population"),
                "sample_size": row.get("sample_size"),
                "response_rate": row.get("response_rate"),
                "margin_of_error": row.get("margin_of_error_text"),
                "method": row.get("method"),
            },
            "result_options": [],
            "adapter_mode": "fallback",
            "adapter_profile": adapter_profile,
            "fallback_applied": False,
        }

        if adapter_row and (adapter_row.get("result_items") or []):
            options = _extract_option_items(adapter_row)
            record["result_options"] = options
            record["adapter_mode"] = adapter_mode
            record["adapter_profile"] = adapter_profile
            record["fallback_applied"] = used_template_fallback
            success_count += 1
            if used_template_fallback:
                template_fallback_count += 1
                fallback_count += 1
                record["collect_status"] = "collected_template_fallback"
            else:
                exact_success_count += 1
            pollster_counter[pollster] += 1

            total_option_count += len(options)
            for opt in options:
                if opt.get("value_raw") and opt.get("value_mid") is not None:
                    normalization_ok_option_count += 1

            if used_template_fallback:
                review_queue_candidates.append(
                    new_review_queue_item(
                        entity_type="poll_observation",
                        entity_id=ntt_id or f"ntt-missing-template-{template_fallback_count}",
                        issue_type="mapping_error",
                        stage="nesdc_safe_collect_v1",
                        error_code="ADAPTER_TEMPLATE_FALLBACK",
                        error_message="exact ntt_id adapter row missing; pollster template fallback applied",
                        source_url=row.get("detail_url"),
                        payload={
                            "ntt_id": ntt_id,
                            "pollster": pollster,
                            "template_ntt_id": str(adapter_row.get("ntt_id") or ""),
                            "release_policy_hours": release_policy_hours,
                        },
                    ).to_dict()
                )
        else:
            fallback_count += 1
            hard_fallback_count += 1
            record["fallback_applied"] = True
            record["collect_status"] = "fallback_collected"
            review_queue_candidates.append(
                new_review_queue_item(
                    entity_type="poll_observation",
                    entity_id=ntt_id or f"ntt-missing-{fallback_count}",
                    issue_type="extract_error",
                    stage="nesdc_safe_collect_v1",
                    error_code="ADAPTER_FALLBACK_APPLIED",
                    error_message="NESDC adapter parse failed or result items missing; fallback record emitted",
                    source_url=row.get("detail_url"),
                    payload={
                        "ntt_id": ntt_id,
                        "pollster": pollster,
                        "release_policy_hours": release_policy_hours,
                    },
                ).to_dict()
            )

        output_records.append(record)

    unique_pollsters = len([k for k, v in pollster_counter.items() if v > 0])
    normalization_ratio = round(normalization_ok_option_count / total_option_count, 4) if total_option_count else 0.0
    adapter_profile_counter = Counter((r.get("adapter_profile") or {}).get("profile_key") for r in output_records)

    recent_registry_count = min(20, len(registry_rows))
    recent_pending = len(pending_records[:recent_registry_count])
    release_policy_violation_count_recent20 = 0
    for rec in output_records[:recent_registry_count]:
        if rec.get("release_gate_passed") is not True:
            release_policy_violation_count_recent20 += 1

    report = {
        "run_type": "collector_nesdc_safe_collect_v1",
        "registry_path": registry_path,
        "adapter_path": adapter_path,
        "as_of_kst": as_of.isoformat(timespec="seconds"),
        "release_policy_hours": {
            "general_hours": general_release_hours,
            "periodical_hours": periodical_release_hours,
        },
        "counts": {
            "registry_total": len(registry_rows),
            "eligible_48h_total": len(eligible_rows),
            "release_gate_eligible_total": len(eligible_rows),
            "pending_official_release_count": len(pending_records),
            "collected_success_count": success_count,
            "adapter_exact_success_count": exact_success_count,
            "adapter_template_success_count": template_fallback_count,
            "fallback_count": fallback_count,
            "template_fallback_count": template_fallback_count,
            "hard_fallback_count": hard_fallback_count,
            "manual_opt_out_count": manual_opt_out_count,
            "eligibility_parse_error_count": eligibility_parse_error_count,
            "safe_window_guard_block_count": safe_window_guard_block_count,
            "review_queue_candidate_count": len(review_queue_candidates),
            "unique_pollster_count": unique_pollsters,
            "total_option_count": total_option_count,
            "recent20_pending_official_release_count": recent_pending,
            "recent20_release_policy_violation_count": release_policy_violation_count_recent20,
        },
        "adapter_profile_counts": dict(adapter_profile_counter),
        "value_normalization": {
            "raw_and_normalized_option_count": normalization_ok_option_count,
            "raw_and_normalized_ratio": normalization_ratio,
        },
        "acceptance_checks": {
            "safe_window_applied_all": len(output_records) == len(eligible_rows),
            "release_gate_applied_all": (
                len(output_records) + len(pending_records) + manual_opt_out_count + eligibility_parse_error_count == len(registry_rows)
            ),
            "pending_nonpublic_state_preserved": all(r.get("collect_status") == "pending_official_release" for r in pending_records),
            "recent20_policy_violation_zero": release_policy_violation_count_recent20 == 0,
            "eligible_collection_success_present": success_count > 0,
            "pollster_coverage_ge_5": unique_pollsters >= 5,
            "fallback_review_queue_synced": (
                fallback_count + eligibility_parse_error_count + safe_window_guard_block_count
                == len(review_queue_candidates)
            ),
            "value_raw_and_normalized_present": normalization_ok_option_count > 0,
        },
    }

    return {
        "data": {
            "run_type": "collector_nesdc_safe_collect_v1",
            "extractor_version": "collector-nesdc-safe-collect-v1",
            "records": output_records,
            "pending_records": pending_records,
        },
        "report": report,
        "review_queue_candidates": review_queue_candidates,
    }


def main() -> None:
    out = generate_nesdc_safe_collect_v1()

    Path(OUT_DATA).write_text(json.dumps(out["data"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_DATA)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()
