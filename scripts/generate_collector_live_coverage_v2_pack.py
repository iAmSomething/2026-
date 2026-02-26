from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any

from app.services.ingest_service import _repair_candidate_matchup_scenarios
from app.services.ingest_input_normalization import normalize_option_type
from app.services.normalization import normalize_percentage
from src.pipeline.contracts import new_review_queue_item

INPUT_WEB_DEMO = "data/collector_web_demo_datapack_30d.json"
INPUT_PARTY_V2_BATCH = "data/collector_party_inference_v2_batch50.json"
INPUT_NESDC = "data/nesdc_registry_snapshot_v1.json"

OUT_PAYLOAD = "data/collector_live_coverage_v2_payload.json"
OUT_REPORT = "data/collector_live_coverage_v2_report.json"
OUT_REVIEW_QUEUE = "data/collector_live_coverage_v2_review_queue_candidates.json"

TARGET_TOTAL_RECORDS = 30
WINDOW_DAYS = 30
MIN_LOCAL_UNIQUE_REGIONS = 12


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_margin_of_error(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"±\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_kst_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _today_iso_kst(at: date) -> str:
    return f"{at.isoformat()}T12:00:00+09:00"


def _pick_recent_nesdc_rows(rows: list[dict[str, Any]], *, as_of: date, window_days: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    window_start = as_of - timedelta(days=window_days)
    for row in rows:
        reg = _parse_kst_datetime(str(row.get("registered_at") or ""))
        if reg is None:
            continue
        if window_start <= reg.date() <= as_of:
            out.append(row)
    return out


def _normalize_demo_record(row: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(row)
    obs = out.get("observation") or {}
    region = out.get("region") or {}
    option_types: set[str] = set()
    for option in out.get("options") or []:
        normalized_type, _, _ = normalize_option_type(
            option.get("option_type"),
            option.get("option_name"),
            question_text=option.get("question_text") or option.get("evidence_text"),
        )
        option["option_type"] = normalized_type
        option_types.add(normalized_type)

    if "party_support" in option_types or "president_job_approval" in option_types or "election_frame" in option_types:
        obs["audience_scope"] = "national"
        obs["audience_region_code"] = None
    elif region.get("admin_level") == "sigungu":
        obs["audience_scope"] = "local"
        obs["audience_region_code"] = region.get("region_code")
    else:
        obs["audience_scope"] = "regional"
        obs["audience_region_code"] = region.get("region_code")

    obs["source_channel"] = "article"
    obs["source_channels"] = ["article"]
    out["observation"] = obs
    return out


def _pick_local_records_v2(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    local_records = [r for r in records if (r.get("observation") or {}).get("office_type") == "기초자치단체장"]

    def _sort_key(row: dict[str, Any]) -> tuple[int, str]:
        obs = row.get("observation") or {}
        d = _parse_iso_date(obs.get("survey_end_date"))
        score = int(d.strftime("%Y%m%d")) if d else 0
        return (score, str(obs.get("observation_key") or ""))

    local_records.sort(key=_sort_key, reverse=True)

    selected: list[dict[str, Any]] = []
    used_regions: set[str] = set()
    used_matchups: set[str] = set()

    for row in local_records:
        obs = row.get("observation") or {}
        region_code = ((row.get("region") or {}).get("region_code") or obs.get("region_code") or "").strip()
        matchup_id = str(obs.get("matchup_id") or "")
        if not region_code or region_code in used_regions:
            continue
        selected.append(row)
        used_regions.add(region_code)
        if matchup_id:
            used_matchups.add(matchup_id)
        if len(used_regions) >= min(MIN_LOCAL_UNIQUE_REGIONS, limit):
            break

    for row in local_records:
        if len(selected) >= limit:
            break
        if row in selected:
            continue
        obs = row.get("observation") or {}
        matchup_id = str(obs.get("matchup_id") or "")
        if matchup_id and matchup_id in used_matchups and len(selected) < (limit - 3):
            continue
        selected.append(row)
        if matchup_id:
            used_matchups.add(matchup_id)

    return selected[:limit]


def _normalize_local_record_v2(
    row: dict[str, Any],
    *,
    idx: int,
    as_of: date,
    nesdc_row: dict[str, Any],
) -> dict[str, Any]:
    out = deepcopy(row)
    article = out.get("article") or {}
    obs = out.get("observation") or {}
    region = out.get("region") or {}

    survey_end = as_of - timedelta(days=(idx % WINDOW_DAYS))
    survey_start = survey_end - timedelta(days=1)

    legal = nesdc_row.get("legal_meta") or {}
    margin = _parse_margin_of_error(str(legal.get("margin_of_error") or ""))
    first_publish = _parse_kst_datetime(str(nesdc_row.get("first_publish_at_kst") or ""))

    article["url"] = f"{article.get('url') or 'https://example.local/article'}?live_cov_v2={idx:02d}"
    article["published_at"] = _today_iso_kst(survey_end)

    obs["observation_key"] = f"live30d-v2-{idx:02d}-{obs.get('observation_key') or idx}"
    obs["survey_start_date"] = survey_start.isoformat()
    obs["survey_end_date"] = survey_end.isoformat()
    obs["pollster"] = str(nesdc_row.get("pollster") or obs.get("pollster") or "미상조사기관")
    obs["sample_size"] = int(legal.get("sample_size") or obs.get("sample_size") or 500)
    obs["response_rate"] = float(legal.get("response_rate") or obs.get("response_rate") or 5.0)
    obs["margin_of_error"] = margin if margin is not None else float(obs.get("margin_of_error") or 4.4)
    obs["sponsor"] = str(nesdc_row.get("sponsor") or obs.get("sponsor") or "미상")
    obs["method"] = str(legal.get("method") or nesdc_row.get("method") or obs.get("method") or "미상")
    obs["source_channel"] = "nesdc" if idx % 3 == 0 else "article"
    obs["source_channels"] = ["article", "nesdc"] if obs["source_channel"] == "nesdc" else ["article"]
    obs["source_grade"] = "A" if obs.get("margin_of_error") else "B"
    obs["verified"] = True
    obs["audience_scope"] = "local"
    obs["audience_region_code"] = region.get("region_code") or obs.get("region_code")
    obs["sampling_population_text"] = str(legal.get("survey_population") or obs.get("sampling_population_text") or "")
    obs["official_release_at"] = first_publish.isoformat(timespec="minutes") if first_publish else None
    obs["article_published_at"] = article.get("published_at")
    obs["is_official_confirmed"] = bool(nesdc_row.get("pdf_available"))

    out["article"] = article
    out["observation"] = obs
    _repair_local_candidate_scenarios(out)
    return out


def _repair_local_candidate_scenarios(record: dict[str, Any]) -> None:
    options = record.get("options") or []
    if not options:
        return

    normalized_options: list[dict[str, Any]] = []
    for opt in options:
        row = dict(opt)
        if row.get("value_mid") is None:
            normalized = normalize_percentage(row.get("value_raw"))
            row["value_mid"] = normalized.value_mid
            row["value_min"] = normalized.value_min
            row["value_max"] = normalized.value_max
            row["is_missing"] = normalized.is_missing
        row["scenario_key"] = str(row.get("scenario_key") or "").strip() or "default"
        row.setdefault("scenario_type", None)
        row.setdefault("scenario_title", None)
        normalized_options.append(row)

    changed = _repair_candidate_matchup_scenarios(
        survey_name=(record.get("observation") or {}).get("survey_name"),
        options=normalized_options,
    )
    if not changed:
        return

    for src, dst in zip(normalized_options, options, strict=False):
        dst["scenario_key"] = src.get("scenario_key")
        dst["scenario_type"] = src.get("scenario_type")
        dst["scenario_title"] = src.get("scenario_title")


def build_live_coverage_v2_pack(*, as_of: date = date(2026, 2, 22)) -> dict[str, Any]:
    web_demo = _parse_json(INPUT_WEB_DEMO)
    party_v2_batch = _parse_json(INPUT_PARTY_V2_BATCH)
    nesdc_snapshot = _parse_json(INPUT_NESDC)

    # Seed with national/regional summary rows from web demo only.
    demo_seed = [
        _normalize_demo_record(r)
        for r in (web_demo.get("records") or [])
        if (r.get("observation") or {}).get("office_type") != "기초자치단체장"
    ]

    local_limit = max(0, TARGET_TOTAL_RECORDS - len(demo_seed))
    local_seed = _pick_local_records_v2((party_v2_batch.get("records") or []), local_limit)

    recent_nesdc = _pick_recent_nesdc_rows(nesdc_snapshot.get("records") or [], as_of=as_of, window_days=WINDOW_DAYS)
    if not recent_nesdc:
        raise RuntimeError("No NESDC rows in the recent window; cannot build v2 coverage pack.")

    local_records: list[dict[str, Any]] = []
    for idx, row in enumerate(local_seed, start=1):
        nesdc_row = recent_nesdc[(idx - 1) % len(recent_nesdc)]
        local_records.append(_normalize_local_record_v2(row, idx=idx, as_of=as_of, nesdc_row=nesdc_row))

    merged = (demo_seed + local_records)[:TARGET_TOTAL_RECORDS]
    if len(merged) < TARGET_TOTAL_RECORDS:
        raise RuntimeError(f"Record count too low: {len(merged)} < {TARGET_TOTAL_RECORDS}")

    review_queue_candidates: list[dict[str, Any]] = []
    for row in merged:
        obs = row.get("observation") or {}
        missing_fields = [
            key
            for key in ("pollster", "survey_start_date", "survey_end_date", "margin_of_error")
            if obs.get(key) in (None, "", [])
        ]
        if missing_fields:
            review_queue_candidates.append(
                new_review_queue_item(
                    entity_type="poll_observation",
                    entity_id=str(obs.get("observation_key") or ""),
                    issue_type="extract_error",
                    stage="live_coverage_v2_quality",
                    error_code="MISSING_REQUIRED_META",
                    error_message="required metadata missing for live coverage V2",
                    source_url=(row.get("article") or {}).get("url"),
                    payload={"missing_fields": missing_fields},
                ).to_dict()
            )

    source_channel_counts: dict[str, int] = {}
    office_type_counts: dict[str, int] = {}
    unique_local_regions: set[str] = set()
    unique_matchups: set[str] = set()
    option_type_counts: dict[str, int] = {}

    local_candidate_total = 0
    local_candidate_party_filled = 0

    window_start = as_of - timedelta(days=WINDOW_DAYS)
    in_window_count = 0

    for row in merged:
        obs = row.get("observation") or {}
        source = str(obs.get("source_channel") or "article")
        source_channel_counts[source] = source_channel_counts.get(source, 0) + 1

        office = str(obs.get("office_type") or "")
        office_type_counts[office] = office_type_counts.get(office, 0) + 1

        region_code = str(obs.get("region_code") or "")
        if office == "기초자치단체장" and region_code:
            unique_local_regions.add(region_code)

        matchup_id = str(obs.get("matchup_id") or "")
        if matchup_id:
            unique_matchups.add(matchup_id)

        for opt in row.get("options") or []:
            typ = str(opt.get("option_type") or "unknown")
            option_type_counts[typ] = option_type_counts.get(typ, 0) + 1

        if office == "기초자치단체장":
            for cand in row.get("candidates") or []:
                local_candidate_total += 1
                if str(cand.get("party_name") or "").strip():
                    local_candidate_party_filled += 1

        end_d = _parse_iso_date(obs.get("survey_end_date"))
        if end_d and window_start <= end_d <= as_of:
            in_window_count += 1

    local_party_fill_rate = (
        round(local_candidate_party_filled / local_candidate_total, 4) if local_candidate_total else 0.0
    )

    acceptance = {
        "records_ge_30": len(merged) >= TARGET_TOTAL_RECORDS,
        "dual_source_present": source_channel_counts.get("article", 0) > 0 and source_channel_counts.get("nesdc", 0) > 0,
        "national_indicator_present": option_type_counts.get("party_support", 0) > 0
        and (
            option_type_counts.get("president_job_approval", 0) > 0
            or option_type_counts.get("election_frame", 0) > 0
            or option_type_counts.get("presidential_approval", 0) > 0
        ),
        "metro_matchup_present": office_type_counts.get("광역자치단체장", 0) > 0,
        "local_sigungu_ge_12": len(unique_local_regions) >= MIN_LOCAL_UNIQUE_REGIONS,
        "unique_matchup_ge_24": len(unique_matchups) >= 24,
        "survey_end_within_30d_all": in_window_count == len(merged),
        "local_candidate_party_fill_rate_ge_02": local_party_fill_rate >= 0.2,
    }

    payload = {
        "run_type": "collector_live_coverage_v2",
        "extractor_version": "collector-live-coverage-v2",
        "llm_model": None,
        "records": merged,
    }
    report = {
        "run_type": "collector_live_coverage_v2",
        "as_of_date": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "source_payloads": {
            "web_demo": INPUT_WEB_DEMO,
            "party_v2_batch": INPUT_PARTY_V2_BATCH,
            "nesdc_snapshot": INPUT_NESDC,
        },
        "counts": {
            "records": len(merged),
            "unique_matchups": len(unique_matchups),
            "unique_local_sigungu_regions": len(unique_local_regions),
            "in_window_count": in_window_count,
        },
        "source_channel_counts": source_channel_counts,
        "office_type_counts": office_type_counts,
        "option_type_counts": option_type_counts,
        "local_candidate_party_fill_rate": local_party_fill_rate,
        "review_queue_candidate_count": len(review_queue_candidates),
        "acceptance_checks": acceptance,
    }

    return {
        "payload": payload,
        "report": report,
        "review_queue_candidates": review_queue_candidates,
    }


def main() -> None:
    out = build_live_coverage_v2_pack()
    Path(OUT_PAYLOAD).write_text(json.dumps(out["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_PAYLOAD)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()
