from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from src.pipeline.contracts import new_review_queue_item

INPUT_SOURCE = "data/bootstrap_ingest_coverage_v2.json"
OUT_BATCH = "data/collector_article_legal_completeness_v1_batch50.json"
OUT_REPORT = "data/collector_article_legal_completeness_v1_report.json"
OUT_REVIEW_QUEUE = "data/collector_article_legal_completeness_v1_review_queue_candidates.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "sponsor",
    "pollster",
    "survey_period",
    "sample_size",
    "response_rate",
    "margin_of_error",
)

SAMPLE_SIZE = 50
THRESHOLD = 0.8

_SPONSOR_RE = re.compile(r"(?:의뢰자|의뢰기관|의뢰처|의뢰)\s*[:：]?\s*([가-힣A-Za-z0-9\(\)\-·\s]{2,40})")


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _extract_sponsor_from_text(article_text: str | None) -> str | None:
    if not article_text:
        return None
    m = _SPONSOR_RE.search(article_text)
    if not m:
        return None
    candidate = " ".join((m.group(1) or "").split()).strip(" .,)")
    if len(candidate) < 2:
        return None
    return candidate


def _is_valid_iso_date(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _is_valid_numeric(field: str, value: Any) -> bool:
    if value is None:
        return False
    try:
        n = float(value)
    except (TypeError, ValueError):
        return False

    if field == "sample_size":
        return n > 0 and float(n).is_integer()
    if field == "response_rate":
        return 0 < n <= 100
    if field == "margin_of_error":
        return 0 < n <= 100
    return False


def _reason_code(missing_fields: list[str], invalid_fields: list[str]) -> str:
    if not missing_fields and not invalid_fields:
        return "COMPLETE"
    if invalid_fields:
        return "ABNORMAL_REQUIRED_FIELD_VALUE"
    if "survey_period" in missing_fields:
        return "MISSING_SURVEY_PERIOD"
    if any(k in missing_fields for k in ("sponsor", "pollster")):
        return "MISSING_SURVEY_ACTOR"
    if any(k in missing_fields for k in ("sample_size", "response_rate", "margin_of_error")):
        return "MISSING_STATISTICAL_META"
    return "MISSING_REQUIRED_FIELDS"


def _field_value(field: str, observation: dict[str, Any], article: dict[str, Any]) -> Any:
    if field == "sponsor":
        obs_value = observation.get("sponsor")
        if isinstance(obs_value, str) and obs_value.strip():
            return obs_value.strip()
        return _extract_sponsor_from_text(article.get("raw_text"))
    if field == "pollster":
        return observation.get("pollster")
    if field == "survey_period":
        start = observation.get("survey_start_date")
        end = observation.get("survey_end_date")
        return {
            "survey_start_date": start,
            "survey_end_date": end,
        }
    if field == "sample_size":
        return observation.get("sample_size")
    if field == "response_rate":
        return observation.get("response_rate")
    if field == "margin_of_error":
        return observation.get("margin_of_error")
    return None


def _field_present_and_valid(field: str, value: Any) -> tuple[bool, bool]:
    if field in {"sponsor", "pollster"}:
        present = isinstance(value, str) and bool(value.strip())
        return present, present

    if field == "survey_period":
        period = value if isinstance(value, dict) else {}
        start_ok = _is_valid_iso_date(period.get("survey_start_date"))
        end_ok = _is_valid_iso_date(period.get("survey_end_date"))
        present = start_ok or end_ok
        valid = present
        return present, valid

    present = value is not None
    valid = _is_valid_numeric(field, value)
    return present, valid


def generate_collector_article_legal_completeness_v1_batch50(
    *,
    source_path: str = INPUT_SOURCE,
    sample_size: int = SAMPLE_SIZE,
    threshold: float = THRESHOLD,
) -> dict[str, Any]:
    payload = _parse_json(source_path)
    rows = list(payload.get("records") or [])[:sample_size]
    if len(rows) < sample_size:
        raise RuntimeError(f"insufficient source records: got={len(rows)} required={sample_size}")

    scored_records: list[dict[str, Any]] = []
    review_queue_candidates: list[dict[str, Any]] = []

    present_counts = Counter()
    valid_counts = Counter()
    missing_counts = Counter()
    invalid_counts = Counter()
    reason_counts = Counter()

    threshold_miss_count = 0

    for idx, row in enumerate(rows):
        article = row.get("article") or {}
        observation = dict(row.get("observation") or {})

        required_schema: dict[str, dict[str, Any]] = {}
        missing_fields: list[str] = []
        invalid_fields: list[str] = []

        for field in REQUIRED_FIELDS:
            value = _field_value(field, observation, article)
            present, valid = _field_present_and_valid(field, value)
            required_schema[field] = {
                "value": value,
                "is_present": present,
                "is_valid": valid,
            }

            if present:
                present_counts[field] += 1
            else:
                missing_counts[field] += 1
                missing_fields.append(field)

            if valid:
                valid_counts[field] += 1
            elif present:
                invalid_counts[field] += 1
                invalid_fields.append(field)

        filled_count = sum(1 for field in REQUIRED_FIELDS if required_schema[field]["is_present"] and required_schema[field]["is_valid"])
        required_count = len(REQUIRED_FIELDS)
        score = round(filled_count / required_count, 4)
        reason_code = _reason_code(missing_fields, invalid_fields)
        reason_counts[reason_code] += 1

        observation["legal_required_schema"] = required_schema
        observation["legal_completeness_score"] = score
        observation["legal_filled_count"] = filled_count
        observation["legal_required_count"] = required_count
        observation["legal_missing_fields"] = missing_fields
        observation["legal_invalid_fields"] = invalid_fields
        observation["legal_reason_code"] = reason_code

        new_row = dict(row)
        new_row["observation"] = observation
        scored_records.append(new_row)

        if score < threshold:
            threshold_miss_count += 1
            review_queue_candidates.append(
                new_review_queue_item(
                    entity_type="poll_observation",
                    entity_id=str(observation.get("observation_key") or f"obs-{idx}"),
                    issue_type="extract_error",
                    stage="legal_completeness_v1",
                    error_code="LEGAL_COMPLETENESS_BELOW_THRESHOLD",
                    error_message="required legal fields completeness below threshold",
                    source_url=article.get("url"),
                    payload={
                        "completeness_score": score,
                        "threshold": threshold,
                        "reason_code": reason_code,
                        "missing_fields": missing_fields,
                        "invalid_fields": invalid_fields,
                    },
                ).to_dict()
            )

    field_rates = {}
    for field in REQUIRED_FIELDS:
        field_rates[field] = {
            "present_count": present_counts[field],
            "present_rate": round(present_counts[field] / sample_size, 4),
            "valid_count": valid_counts[field],
            "valid_rate": round(valid_counts[field] / sample_size, 4),
            "missing_count": missing_counts[field],
            "missing_rate": round(missing_counts[field] / sample_size, 4),
            "invalid_count": invalid_counts[field],
            "invalid_rate": round(invalid_counts[field] / sample_size, 4),
        }

    avg_score = round(
        sum((r.get("observation") or {}).get("legal_completeness_score") or 0.0 for r in scored_records) / sample_size,
        4,
    )

    report = {
        "run_type": "collector_article_legal_completeness_v1",
        "source_path": source_path,
        "sample_size": sample_size,
        "required_fields": list(REQUIRED_FIELDS),
        "threshold": threshold,
        "completeness": {
            "avg_score": avg_score,
            "min_score": min((r.get("observation") or {}).get("legal_completeness_score") or 0.0 for r in scored_records),
            "max_score": max((r.get("observation") or {}).get("legal_completeness_score") or 0.0 for r in scored_records),
            "threshold_miss_count": threshold_miss_count,
            "threshold_miss_rate": round(threshold_miss_count / sample_size, 4),
        },
        "field_rates": field_rates,
        "reason_code_counts": dict(reason_counts),
        "review_queue_candidate_count": len(review_queue_candidates),
        "acceptance_checks": {
            "sample_size_eq_50": sample_size == 50,
            "threshold_miss_review_queue_synced": len(review_queue_candidates) == threshold_miss_count,
            "has_missing_or_abnormal_cases": threshold_miss_count > 0,
        },
    }

    batch = {
        "run_type": "collector_article_legal_completeness_v1",
        "extractor_version": "collector-legal-completeness-v1",
        "source_payload": source_path,
        "threshold": threshold,
        "required_fields": list(REQUIRED_FIELDS),
        "records": scored_records,
    }

    return {
        "batch": batch,
        "report": report,
        "review_queue_candidates": review_queue_candidates,
    }


def main() -> None:
    out = generate_collector_article_legal_completeness_v1_batch50()
    Path(OUT_BATCH).write_text(json.dumps(out["batch"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_BATCH)
    print("written:", OUT_REPORT)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()
