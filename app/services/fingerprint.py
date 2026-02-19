from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256

from app.services.errors import DuplicateConflictError

SOURCE_PRIORITY = {"article": 1, "nesdc": 2}


def _norm_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return " ".join(text.split())


def _norm_int(value) -> str:
    if value is None:
        return ""
    return str(int(value))


def _norm_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return _norm_text(value)


def build_poll_fingerprint(observation: dict) -> str:
    fields = [
        _norm_text(observation.get("pollster")),
        _norm_text(observation.get("sponsor")),
        _norm_date(observation.get("survey_start_date")),
        _norm_date(observation.get("survey_end_date")),
        _norm_text(observation.get("region_code") or observation.get("region_text")),
        _norm_int(observation.get("sample_size")),
        _norm_text(observation.get("method")),
    ]
    base = "|".join(fields)
    return sha256(base.encode("utf-8")).hexdigest()


def merge_observation_by_priority(existing: dict, incoming: dict) -> dict:
    existing_source = (existing.get("source_channel") or "article").lower()
    incoming_source = (incoming.get("source_channel") or "article").lower()
    existing_pri = SOURCE_PRIORITY.get(existing_source, 1)
    incoming_pri = SOURCE_PRIORITY.get(incoming_source, 1)

    core_conflicts: list[str] = []
    for field in ("region_code", "office_type", "survey_start_date", "survey_end_date", "sample_size"):
        old = existing.get(field)
        new = incoming.get(field)
        if old not in (None, "") and new not in (None, "") and old != new:
            core_conflicts.append(field)
    if core_conflicts:
        raise DuplicateConflictError(f"DUPLICATE_CONFLICT core fields mismatch: {','.join(core_conflicts)}")

    merged = dict(existing)
    incoming_wins = incoming_pri > existing_pri

    meta_fields = (
        "pollster",
        "sponsor",
        "survey_start_date",
        "survey_end_date",
        "sample_size",
        "response_rate",
        "margin_of_error",
        "region_code",
        "office_type",
        "matchup_id",
        "audience_scope",
        "audience_region_code",
        "sampling_population_text",
        "legal_completeness_score",
        "legal_filled_count",
        "legal_required_count",
        "date_resolution",
        "method",
    )
    for field in meta_fields:
        existing_value = existing.get(field)
        incoming_value = incoming.get(field)
        primary = incoming_value if incoming_wins else existing_value
        secondary = existing_value if incoming_wins else incoming_value
        merged[field] = primary if primary not in (None, "") else secondary

    merged["source_channel"] = "nesdc" if "nesdc" in (existing_source, incoming_source) else "article"
    merged["poll_fingerprint"] = incoming.get("poll_fingerprint") or existing.get("poll_fingerprint")
    merged["observation_key"] = existing.get("observation_key") or incoming.get("observation_key")
    merged["verified"] = bool(existing.get("verified")) or bool(incoming.get("verified"))
    merged["source_grade"] = incoming.get("source_grade") or existing.get("source_grade")
    merged["ingestion_run_id"] = incoming.get("ingestion_run_id") or existing.get("ingestion_run_id")

    # Context/document fields: keep article context when available.
    if incoming_source == "article" and incoming.get("survey_name"):
        merged["survey_name"] = incoming.get("survey_name")
        merged["article_id"] = incoming.get("article_id") or existing.get("article_id")
    elif existing.get("survey_name") in (None, "") and incoming.get("survey_name"):
        merged["survey_name"] = incoming.get("survey_name")
    else:
        merged["survey_name"] = existing.get("survey_name") or incoming.get("survey_name")
        merged["article_id"] = existing.get("article_id") or incoming.get("article_id")

    return merged

