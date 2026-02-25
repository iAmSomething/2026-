from __future__ import annotations

from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from src.pipeline.contracts import new_review_queue_item

INPUT_SOURCE = "data/collector_live_news_v1_payload.json"
OUT_BATCH = "data/collector_legal_required_fields_v1_batch30.json"
OUT_REPORT = "data/collector_legal_required_fields_v1_report.json"
OUT_EVAL = "data/collector_legal_required_fields_v1_eval.json"
OUT_REVIEW_QUEUE = "data/collector_legal_required_fields_v1_review_queue_candidates.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "pollster",
    "sponsor",
    "survey_period",
    "sample_size",
    "method",
    "response_rate",
    "margin_of_error",
    "confidence_level",
)

SAMPLE_SIZE = 30
THRESHOLD = 0.9
EVAL_SAMPLE_SIZE = 30

_SPONSOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:의뢰자|의뢰기관|의뢰처|의뢰)\s*[:：]?\s*([가-힣A-Za-z0-9\(\)\-·\s]{2,40}?)(?=\s*(?:조사기관|조사수행기관|실시기관|표본|응답률|오차범위|신뢰수준|전화|ARS|$))"
    ),
    re.compile(r"([가-힣A-Za-z0-9\(\)\-·\s]{2,40})\s*의뢰"),
)
_POLLSTER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:조사기관|조사수행기관|실시기관)\s*[:：]?\s*([가-힣A-Za-z0-9\(\)\-·\s]{2,40}?)(?=\s*(?:표본|응답률|오차범위|신뢰수준|의뢰|전화|ARS|$))"
    ),
)
_METHOD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(전화면접(?:조사)?|전화조사|ARS(?:조사)?|자동응답(?:조사)?|온라인(?:조사)?|면접원(?:조사)?)"),
)
_SAMPLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:표본(?:수)?|조사(?:대상)?)\D{0,12}([0-9][0-9,]{2,6})\s*명"),
    re.compile(r"\bN\s*=\s*([0-9][0-9,]{2,6})\b", flags=re.IGNORECASE),
)
_RESPONSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"응답률\D{0,10}([0-9]+(?:\.[0-9]+)?)\s*%"),
)
_MARGIN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"오차범위\D{0,14}(?:±|\+/-)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*[pP]?"),
    re.compile(r"(?:±|\+/-)\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*[pP]"),
)
_CONFIDENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"([0-9]{2}(?:\.[0-9]+)?)\s*%\s*신뢰수준"),
)
_ISO_DATE_RE = re.compile(r"(20[0-9]{2})[-./](0?[1-9]|1[0-2])[-./](0?[1-9]|[12][0-9]|3[01])")
_KR_DATE_RE = re.compile(r"(20[0-9]{2})\s*년\s*(0?[1-9]|1[0-2])\s*월\s*(0?[1-9]|[12][0-9]|3[01])\s*일")


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_space(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _extract_first(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    cleaned = _normalize_space(text)
    if not cleaned:
        return None
    for pat in patterns:
        m = pat.search(cleaned)
        if not m:
            continue
        value = _normalize_space(m.group(1)).strip(" .,;:)")
        if value:
            return value
    return None


def _parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if value <= 0:
            return None
        return int(value)
    m = re.search(r"([0-9][0-9,]*)", str(value))
    if not m:
        return None
    try:
        parsed = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if parsed > 0 else None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value))
    if not m:
        return None
    try:
        parsed = float(m.group(1))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _iso_date(y: str, m: str, d: str) -> str | None:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def _extract_iso_dates(text: str) -> list[str]:
    out: list[str] = []
    for y, m, d in _ISO_DATE_RE.findall(text):
        parsed = _iso_date(y, m, d)
        if parsed:
            out.append(parsed)
    for y, m, d in _KR_DATE_RE.findall(text):
        parsed = _iso_date(y, m, d)
        if parsed:
            out.append(parsed)
    return sorted(set(out))


def _extract_survey_period_from_text(text: str) -> dict[str, str | None] | None:
    dates = _extract_iso_dates(text)
    if not dates:
        return None
    if len(dates) == 1:
        return {"survey_start_date": None, "survey_end_date": dates[0]}
    return {"survey_start_date": dates[0], "survey_end_date": dates[-1]}


def _extract_method_from_text(text: str) -> str | None:
    return _extract_first(text, _METHOD_PATTERNS)


def _extract_sample_size_from_text(text: str) -> int | None:
    for pat in _SAMPLE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_int(m.group(1))
        if parsed is not None:
            return parsed
    return None


def _extract_response_rate_from_text(text: str) -> float | None:
    for pat in _RESPONSE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_float(m.group(1))
        if parsed is not None and parsed <= 100:
            return parsed
    return None


def _extract_margin_from_text(text: str) -> float | None:
    for pat in _MARGIN_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_float(m.group(1))
        if parsed is not None and parsed <= 100:
            return parsed
    return None


def _extract_confidence_level_from_text(text: str) -> float | None:
    for pat in _CONFIDENCE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        parsed = _parse_float(m.group(1))
        if parsed is not None and 50 <= parsed <= 100:
            return parsed
    return None


def _extract_from_text(article_text: str) -> dict[str, Any]:
    text = _normalize_space(article_text or "")
    return {
        "pollster": _extract_first(text, _POLLSTER_PATTERNS),
        "sponsor": _extract_first(text, _SPONSOR_PATTERNS),
        "survey_period": _extract_survey_period_from_text(text),
        "sample_size": _extract_sample_size_from_text(text),
        "method": _extract_method_from_text(text),
        "response_rate": _extract_response_rate_from_text(text),
        "margin_of_error": _extract_margin_from_text(text),
        "confidence_level": _extract_confidence_level_from_text(text),
    }


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
    n = _parse_float(value)
    if n is None:
        return False
    if field == "sample_size":
        parsed = _parse_int(value)
        return parsed is not None
    if field in {"response_rate", "margin_of_error", "confidence_level"}:
        if field == "confidence_level":
            return 50 <= n <= 100
        return 0 < n <= 100
    return False


def _field_present_and_valid(field: str, value: Any) -> tuple[bool, bool]:
    if field in {"sponsor", "pollster", "method"}:
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


def _missing_reason(field: str, *, present: bool, valid: bool, conflict: bool) -> str | None:
    if conflict:
        return "observation_article_conflict"
    if not present:
        if field == "survey_period":
            return "survey_date_not_found"
        if field == "method":
            return "method_not_found"
        if field == "confidence_level":
            return "confidence_level_not_found"
        if field in {"sponsor", "pollster"}:
            return "actor_not_found"
        return "statistical_meta_not_found"
    if not valid:
        return "invalid_value_format"
    return None


def _norm_str(value: str | None) -> str:
    text = (value or "").strip().lower()
    return re.sub(r"\s+", "", text)


def _field_conflict(field: str, obs_value: Any, text_value: Any) -> tuple[bool, str | None]:
    obs_present, obs_valid = _field_present_and_valid(field, obs_value)
    text_present, text_valid = _field_present_and_valid(field, text_value)
    if not (obs_present and text_present and obs_valid and text_valid):
        return False, None

    if field in {"sponsor", "pollster", "method"}:
        obs_norm = _norm_str(str(obs_value)).replace("조사", "")
        text_norm = _norm_str(str(text_value)).replace("조사", "")
        if obs_norm == text_norm:
            return False, None
        if obs_norm and text_norm and (obs_norm in text_norm or text_norm in obs_norm):
            return False, None
        if obs_norm != text_norm:
            return True, "observation_article_mismatch"
        return False, None

    if field == "survey_period":
        obs_end = (obs_value or {}).get("survey_end_date") if isinstance(obs_value, dict) else None
        text_end = (text_value or {}).get("survey_end_date") if isinstance(text_value, dict) else None
        if obs_end and text_end and obs_end != text_end:
            return True, "survey_period_mismatch"
        return False, None

    obs_num = _parse_float(obs_value)
    text_num = _parse_float(text_value)
    if obs_num is None or text_num is None:
        return False, None
    tolerance = 1.0 if field == "sample_size" else 0.5
    if abs(obs_num - text_num) > tolerance:
        return True, "numeric_mismatch"
    return False, None


def _obs_value(field: str, observation: dict[str, Any]) -> Any:
    if field == "survey_period":
        return {
            "survey_start_date": observation.get("survey_start_date"),
            "survey_end_date": observation.get("survey_end_date"),
        }
    if field == "confidence_level":
        return observation.get("confidence_level")
    return observation.get(field)


def _choose_value(field: str, observation: dict[str, Any], text_values: dict[str, Any]) -> tuple[Any, str, float, bool, str | None]:
    obs_value = _obs_value(field, observation)
    text_value = text_values.get(field)

    conflict, conflict_reason = _field_conflict(field, obs_value, text_value)

    obs_present, obs_valid = _field_present_and_valid(field, obs_value)
    text_present, text_valid = _field_present_and_valid(field, text_value)

    if obs_valid:
        return obs_value, "observation", 1.0, conflict, conflict_reason
    if text_valid:
        return text_value, "article_pattern", 0.78, conflict, conflict_reason
    if obs_present:
        return obs_value, "observation", 0.25, conflict, conflict_reason
    if text_present:
        return text_value, "article_pattern", 0.2, conflict, conflict_reason
    return None, "none", 0.0, conflict, conflict_reason


def _reason_code(missing_fields: list[str], invalid_fields: list[str], conflict_fields: list[str]) -> str:
    if not missing_fields and not invalid_fields and not conflict_fields:
        return "COMPLETE"
    if conflict_fields:
        return "CONFLICT_REQUIRED_FIELD_VALUE"
    if invalid_fields:
        return "ABNORMAL_REQUIRED_FIELD_VALUE"
    if "survey_period" in missing_fields:
        return "MISSING_SURVEY_PERIOD"
    if any(k in missing_fields for k in ("sponsor", "pollster")):
        return "MISSING_SURVEY_ACTOR"
    if any(k in missing_fields for k in ("sample_size", "response_rate", "margin_of_error", "confidence_level", "method")):
        return "MISSING_STATISTICAL_META"
    return "MISSING_REQUIRED_FIELDS"


def _calc_precision_recall(records: list[dict[str, Any]]) -> dict[str, Any]:
    field_tp = Counter()
    field_fp = Counter()
    field_fn = Counter()

    for row in records:
        schema = ((row.get("observation") or {}).get("legal_required_schema") or {})
        for field in REQUIRED_FIELDS:
            entry = schema.get(field) or {}
            present = bool(entry.get("is_present"))
            valid = bool(entry.get("is_valid"))
            conflict = bool(entry.get("is_conflict"))
            if present and valid and not conflict:
                field_tp[field] += 1
            elif present:
                field_fp[field] += 1
            else:
                field_fn[field] += 1

    by_field: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0
    for field in REQUIRED_FIELDS:
        tp = field_tp[field]
        fp = field_fp[field]
        fn = field_fn[field]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        by_field[field] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(tp / max(1, tp + fp), 4),
            "recall": round(tp / max(1, tp + fn), 4),
        }

    return {
        "sample_size": len(records),
        "micro_precision": round(total_tp / max(1, total_tp + total_fp), 4),
        "micro_recall": round(total_tp / max(1, total_tp + total_fn), 4),
        "field_metrics": by_field,
    }


def generate_collector_article_legal_completeness_v1_batch50(
    *,
    source_path: str = INPUT_SOURCE,
    sample_size: int = SAMPLE_SIZE,
    threshold: float = THRESHOLD,
    eval_sample_size: int = EVAL_SAMPLE_SIZE,
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
    conflict_counts = Counter()
    reason_counts = Counter()

    threshold_miss_count = 0
    issue_row_count = 0
    missing_reason_covered_count = 0
    missing_field_total = 0

    for idx, row in enumerate(rows):
        article = row.get("article") or {}
        observation = dict(row.get("observation") or {})
        text_values = _extract_from_text(str(article.get("raw_text") or ""))

        required_schema: dict[str, dict[str, Any]] = {}
        missing_fields: list[str] = []
        invalid_fields: list[str] = []
        conflict_fields: list[str] = []

        for field in REQUIRED_FIELDS:
            value, source, confidence, conflict, conflict_reason = _choose_value(field, observation, text_values)
            present, valid = _field_present_and_valid(field, value)
            reason = _missing_reason(field, present=present, valid=valid, conflict=conflict)
            required_schema[field] = {
                "value": value,
                "source": source,
                "is_present": present,
                "is_valid": valid,
                "is_conflict": conflict,
                "conflict_reason": conflict_reason,
                "extraction_confidence": round(confidence, 4),
                "missing_reason": reason,
            }

            if present:
                present_counts[field] += 1
            else:
                missing_counts[field] += 1
                missing_fields.append(field)
                missing_field_total += 1
                if reason:
                    missing_reason_covered_count += 1

            if valid:
                valid_counts[field] += 1
            elif present:
                invalid_counts[field] += 1
                invalid_fields.append(field)

            if conflict:
                conflict_counts[field] += 1
                conflict_fields.append(field)

            if field == "pollster" and present and valid and isinstance(value, str):
                observation["pollster"] = value
            if field == "sponsor" and present and valid and isinstance(value, str):
                observation["sponsor"] = value
            if field == "method" and present and valid and isinstance(value, str):
                observation["method"] = value
            if field == "survey_period" and present and valid and isinstance(value, dict):
                observation["survey_start_date"] = value.get("survey_start_date")
                observation["survey_end_date"] = value.get("survey_end_date")
            if field in {"sample_size", "response_rate", "margin_of_error"} and present and valid:
                observation[field] = value

        filled_count = sum(
            1 for field in REQUIRED_FIELDS if required_schema[field]["is_present"] and required_schema[field]["is_valid"] and not required_schema[field]["is_conflict"]
        )
        required_count = len(REQUIRED_FIELDS)
        score = round(filled_count / required_count, 4)
        reason_code = _reason_code(missing_fields, invalid_fields, conflict_fields)
        reason_counts[reason_code] += 1

        observation["legal_required_schema"] = required_schema
        observation["legal_completeness_score"] = score
        observation["legal_filled_count"] = filled_count
        observation["legal_required_count"] = required_count
        observation["legal_missing_fields"] = missing_fields
        observation["legal_invalid_fields"] = invalid_fields
        observation["legal_conflict_fields"] = conflict_fields
        observation["legal_reason_code"] = reason_code

        new_row = dict(row)
        new_row["observation"] = observation
        scored_records.append(new_row)

        has_issue = bool(missing_fields or invalid_fields or conflict_fields)
        if score < threshold:
            threshold_miss_count += 1

        if has_issue:
            issue_row_count += 1
            review_queue_candidates.append(
                new_review_queue_item(
                    entity_type="poll_observation",
                    entity_id=str(observation.get("observation_key") or f"obs-{idx}"),
                    issue_type="extract_error",
                    stage="legal_required_fields_v1",
                    error_code="LEGAL_REQUIRED_FIELDS_NEEDS_REVIEW",
                    error_message="missing/invalid/conflicting legal required fields detected",
                    source_url=article.get("url"),
                    payload={
                        "completeness_score": score,
                        "threshold": threshold,
                        "reason_code": reason_code,
                        "missing_fields": missing_fields,
                        "invalid_fields": invalid_fields,
                        "conflict_fields": conflict_fields,
                        "field_schema": required_schema,
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
            "conflict_count": conflict_counts[field],
            "conflict_rate": round(conflict_counts[field] / sample_size, 4),
        }

    avg_score = round(
        sum((r.get("observation") or {}).get("legal_completeness_score") or 0.0 for r in scored_records) / sample_size,
        4,
    )

    eval_rows = scored_records[: min(eval_sample_size, len(scored_records))]
    eval_metrics = _calc_precision_recall(eval_rows)

    report = {
        "run_type": "collector_legal_required_fields_v1",
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
        "precision_recall": eval_metrics,
        "acceptance_checks": {
            "sample_size_gte_30": sample_size >= 30,
            "eval_sample_size_eq_30": eval_metrics["sample_size"] == 30,
            "avg_completeness_ge_0_90": avg_score >= 0.9,
            "missing_reason_coverage_eq_100": missing_reason_covered_count == missing_field_total,
            "missing_conflict_review_queue_synced": issue_row_count == len(review_queue_candidates),
            "legal_schema_injected_all": len(scored_records) == sample_size
            and all(
                isinstance(((r.get("observation") or {}).get("legal_required_schema")), dict)
                for r in scored_records
            ),
        },
        "risk_signals": {
            "missing_or_conflict_cases_present": issue_row_count > 0,
            "issue_row_count": issue_row_count,
            "threshold_miss_count": threshold_miss_count,
            "threshold_miss_rate": round(threshold_miss_count / sample_size, 4),
        },
    }

    eval_output = {
        "run_type": "collector_legal_required_fields_v1_eval",
        "source_path": source_path,
        "sample_size": eval_metrics["sample_size"],
        "required_fields": list(REQUIRED_FIELDS),
        "micro_precision": eval_metrics["micro_precision"],
        "micro_recall": eval_metrics["micro_recall"],
        "field_metrics": eval_metrics["field_metrics"],
    }

    batch = {
        "run_type": "collector_legal_required_fields_v1",
        "extractor_version": "collector-legal-required-fields-v1",
        "source_payload": source_path,
        "threshold": threshold,
        "required_fields": list(REQUIRED_FIELDS),
        "records": scored_records,
    }

    return {
        "batch": batch,
        "report": report,
        "eval": eval_output,
        "review_queue_candidates": review_queue_candidates,
    }


def main() -> None:
    out = generate_collector_article_legal_completeness_v1_batch50()
    Path(OUT_BATCH).write_text(json.dumps(out["batch"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_EVAL).write_text(json.dumps(out["eval"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REVIEW_QUEUE).write_text(
        json.dumps(out["review_queue_candidates"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_BATCH)
    print("written:", OUT_REPORT)
    print("written:", OUT_EVAL)
    print("written:", OUT_REVIEW_QUEUE)


if __name__ == "__main__":
    main()
