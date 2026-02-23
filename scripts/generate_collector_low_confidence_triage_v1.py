from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

INPUT_PATHS = (
    "data/bootstrap_ingest_coverage_v2_review_queue_candidates.json",
    "data/collector_scope_inference_v1_batch.json",
    "data/collector_party_inference_v2_batch50.json",
    "data/collector_enrichment_v2_batch.json",
    "data/collector_live_coverage_v2_review_queue_candidates.json",
)

OUT_TRIAGE = "data/collector_low_confidence_triage_v1.json"
OUT_SUMMARY = "data/collector_low_confidence_triage_v1_summary.json"


def _load_items(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    payload = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("review_queue_candidates"), list):
            return [x for x in payload.get("review_queue_candidates") if isinstance(x, dict)]
    return []


def _extract_low_confidence_score(item: dict[str, Any]) -> float | None:
    payload = item.get("payload") or {}
    for key in ("party_inference_confidence", "scope_confidence", "confidence_score"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _route(item: dict[str, Any]) -> tuple[int, str, str, int, str]:
    issue_type = str(item.get("issue_type") or "")
    error_code = str(item.get("error_code") or "")

    if error_code in {"AUDIENCE_SCOPE_CONFLICT_POPULATION", "PARTY_INFERENCE_CONFLICT_SIGNALS"}:
        return 15, "conflict-high-risk", "immediate_review", 12, "conflict signal must be reviewed first"

    if error_code in {"AUDIENCE_SCOPE_LOW_CONFIDENCE", "PARTY_INFERENCE_LOW_CONFIDENCE"}:
        return 20, "low-confidence-model", "immediate_review", 24, "model confidence below policy threshold"

    if error_code in {"PARTY_INFERENCE_INVALID_CANDIDATE", "PARTY_INFERENCE_NO_SIGNAL", "NESDC_ENRICH_V2_NO_MATCH"}:
        return 40, "low-signal-backlog", "defer_requeue", 72, "insufficient signal; defer and retry after refresh"

    if error_code == "ROBOTS_BLOCKLIST_BYPASS":
        return 90, "known-noise", "drop_noise", 72, "known robots blocklist noise"

    if issue_type == "discover_error":
        return 60, "discover", "defer_requeue", 12, "discover error needs later retry"

    if issue_type == "fetch_error":
        return 50, "fetch", "defer_requeue", 24, "fetch error needs delayed retry"

    if issue_type == "classify_error":
        return 45, "classify", "immediate_review", 24, "classification failure"

    if issue_type == "extract_error":
        return 30, "extract", "immediate_review", 24, "extraction failure"

    if issue_type == "mapping_error":
        return 25, "mapping", "immediate_review", 24, "mapping mismatch"

    return 70, "other", "immediate_review", 48, "fallback triage"


def build_low_confidence_triage_v1(*, input_paths: tuple[str, ...] = INPUT_PATHS) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for path in input_paths:
        for item in _load_items(path):
            issue_type = str(item.get("issue_type") or "")
            error_code = str(item.get("error_code") or "")
            entity_id = str(item.get("entity_id") or "")
            source_url = str(item.get("source_url") or "")
            dedup_key = (issue_type, error_code, entity_id, source_url)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            triage_priority, triage_bucket, route_action, sla_hours, reason = _route(item)
            low_conf_score = _extract_low_confidence_score(item)

            merged.append(
                {
                    **item,
                    "source_input": path,
                    "triage_priority": triage_priority,
                    "triage_bucket": triage_bucket,
                    "route_action": route_action,
                    "sla_hours": sla_hours,
                    "routing_reason": reason,
                    "low_confidence_score": low_conf_score,
                }
            )

    merged.sort(
        key=lambda x: (
            int(x.get("triage_priority") or 999),
            str(x.get("issue_type") or ""),
            str(x.get("error_code") or ""),
            str(x.get("source_url") or ""),
        )
    )

    bucket_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    code_counter: Counter[str] = Counter()

    low_conf_items = 0
    for item in merged:
        bucket_counter[str(item.get("triage_bucket") or "unknown")] += 1
        action_counter[str(item.get("route_action") or "unknown")] += 1
        code_counter[str(item.get("error_code") or "unknown")] += 1
        if item.get("low_confidence_score") is not None:
            low_conf_items += 1

    summary = {
        "input_paths": list(input_paths),
        "total_items": len(merged),
        "low_confidence_scored_items": low_conf_items,
        "bucket_distribution": dict(bucket_counter),
        "route_action_distribution": dict(action_counter),
        "error_code_top10": [{"type": k, "count": v} for k, v in code_counter.most_common(10)],
        "acceptance_checks": {
            "triage_fields_present": all(
                all(k in row for k in ("triage_priority", "triage_bucket", "route_action", "sla_hours"))
                for row in merged
            ),
            "conflict_routed_high_priority": all(
                row.get("triage_priority", 999) <= 20
                for row in merged
                if row.get("error_code") in {"AUDIENCE_SCOPE_CONFLICT_POPULATION", "PARTY_INFERENCE_CONFLICT_SIGNALS"}
            ),
            "low_confidence_has_immediate_or_defer": all(
                row.get("route_action") in {"immediate_review", "defer_requeue"}
                for row in merged
                if row.get("error_code")
                in {
                    "AUDIENCE_SCOPE_LOW_CONFIDENCE",
                    "PARTY_INFERENCE_LOW_CONFIDENCE",
                    "PARTY_INFERENCE_NO_SIGNAL",
                }
            ),
        },
    }

    return {"triage": merged, "summary": summary}


def main() -> None:
    out = build_low_confidence_triage_v1()
    Path(OUT_TRIAGE).write_text(json.dumps(out["triage"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_SUMMARY).write_text(json.dumps(out["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    print("written:", OUT_TRIAGE)
    print("written:", OUT_SUMMARY)


if __name__ == "__main__":
    main()
