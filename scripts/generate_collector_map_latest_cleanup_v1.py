from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from app.api.routes import (
    _build_scope_breakdown,
    _is_legacy_matchup_title,
    _is_map_latest_noise_option_name,
    _map_latest_exclusion_reason,
)
from src.pipeline.contracts import new_review_queue_item

API_BASE = "https://2026-api-production.up.railway.app"
LIMIT = 30

OUT_BEFORE = "data/collector_map_latest_cleanup_v1_before.json"
OUT_AFTER = "data/collector_map_latest_cleanup_v1_after.json"
OUT_REPORT = "data/collector_map_latest_cleanup_v1_report.json"
OUT_REVIEW_QUEUE = "data/collector_map_latest_cleanup_v1_review_queue_candidates.json"


def _write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fetch_map_latest(*, api_base: str = API_BASE, limit: int = LIMIT) -> dict[str, Any]:
    query = urlencode({"limit": str(limit)})
    url = f"{api_base.rstrip('/')}/api/v1/dashboard/map-latest?{query}"
    with urlopen(url, timeout=60) as resp:
        body = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError("map-latest response must be object")
    return payload


def _reason_to_review_meta(reason: str) -> tuple[str, str]:
    if reason == "invalid_candidate_option_name":
        return "classify_error", "MAP_LATEST_INVALID_OPTION_NAME"
    if reason == "legacy_matchup_title":
        return "mapping_error", "MAP_LATEST_LEGACY_TITLE_BLOCK"
    if reason == "survey_end_date_before_cutoff":
        return "ingestion_error", "MAP_LATEST_SURVEY_END_CUTOFF_BLOCK"
    if reason == "article_published_at_before_cutoff":
        return "ingestion_error", "ARTICLE_PUBLISHED_AT_CUTOFF_BLOCK"
    return "ingestion_error", "MAP_LATEST_POLICY_BLOCK"


def apply_map_latest_cleanup(items: list[dict[str, Any]]) -> dict[str, Any]:
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    review_queue_candidates: list[dict[str, Any]] = []

    for row in items:
        reason = _map_latest_exclusion_reason(row)
        if reason is None:
            kept.append(row)
            continue

        reason_counts[reason] += 1
        excluded_row = dict(row)
        excluded_row["excluded_reason"] = reason
        excluded.append(excluded_row)

        issue_type, error_code = _reason_to_review_meta(reason)
        entity_id = "|".join(
            [
                str(row.get("region_code") or ""),
                str(row.get("office_type") or ""),
                str(row.get("survey_end_date") or ""),
                str(row.get("option_name") or ""),
            ]
        )
        review_queue_candidates.append(
            new_review_queue_item(
                entity_type="map_latest_item",
                entity_id=entity_id,
                issue_type=issue_type,
                stage="map_latest_cleanup_v1",
                error_code=error_code,
                error_message=reason,
                source_url=None,
                payload={
                    "region_code": row.get("region_code"),
                    "office_type": row.get("office_type"),
                    "title": row.get("title"),
                    "survey_end_date": row.get("survey_end_date"),
                    "option_name": row.get("option_name"),
                },
            ).to_dict()
        )

    non_human_before = sum(1 for row in items if _is_map_latest_noise_option_name(row.get("option_name")))
    non_human_after = sum(1 for row in kept if _is_map_latest_noise_option_name(row.get("option_name")))
    legacy_before = sum(1 for row in items if _is_legacy_matchup_title(row.get("title")))
    legacy_after = sum(1 for row in kept if _is_legacy_matchup_title(row.get("title")))

    return {
        "kept_items": kept,
        "excluded_items": excluded,
        "excluded_reason_counts": dict(reason_counts),
        "review_queue_candidates": review_queue_candidates,
        "stats": {
            "before_count": len(items),
            "after_count": len(kept),
            "excluded_count": len(excluded),
            "non_human_option_count_before": non_human_before,
            "non_human_option_count_after": non_human_after,
            "legacy_title_count_before": legacy_before,
            "legacy_title_count_after": legacy_after,
        },
    }


def main() -> None:
    before = _fetch_map_latest(limit=LIMIT)
    before_items = list(before.get("items") or [])

    cleanup = apply_map_latest_cleanup(before_items)
    after_items = cleanup["kept_items"]

    after_payload = {
        "as_of": before.get("as_of"),
        "items": after_items,
        "scope_breakdown": _build_scope_breakdown(after_items),
    }
    report = {
        "run_type": "collector_map_latest_cleanup_v1",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "api_base": API_BASE,
        "sample_limit": LIMIT,
        "stats": cleanup["stats"],
        "excluded_reason_counts": cleanup["excluded_reason_counts"],
        "acceptance_checks": {
            "top30_non_human_option_zero_after": cleanup["stats"]["non_human_option_count_after"] == 0,
            "top30_legacy_title_zero_after": cleanup["stats"]["legacy_title_count_after"] == 0,
        },
    }

    _write_json(OUT_BEFORE, before)
    _write_json(OUT_AFTER, after_payload)
    _write_json(OUT_REPORT, report)
    _write_json(OUT_REVIEW_QUEUE, cleanup["review_queue_candidates"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("written:", OUT_BEFORE)
    print("written:", OUT_AFTER)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()
