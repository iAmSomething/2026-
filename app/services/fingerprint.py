from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256

from app.services.errors import DuplicateConflictError

SOURCE_PRIORITY = {"article": 1, "nesdc": 2}
SOURCE_GRADE_PRIORITY = {"A": 4, "B": 3, "C": 2, "D": 1}


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
    text = _norm_text(value)
    if not text:
        return ""
    text = text.replace(".", "-").replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return text


def build_poll_fingerprint(observation: dict) -> str:
    fields = [
        _norm_text(observation.get("pollster")),
        _norm_text(observation.get("sponsor")),
        _norm_date(observation.get("survey_start_date")),
        _norm_date(observation.get("survey_end_date")),
        _norm_text(observation.get("region_code") or observation.get("region_text")),
        _norm_int(observation.get("sample_size")),
        _norm_text(observation.get("method")),
        _norm_text(observation.get("poll_block_id")),
    ]
    base = "|".join(fields)
    return sha256(base.encode("utf-8")).hexdigest()


def _normalize_channels(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        text = value.strip().lower().strip("{}")
        if not text:
            return set()
        candidates = [x.strip() for x in text.split(",")]
        return {x for x in candidates if x in SOURCE_PRIORITY}

    out: set[str] = set()
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if item is None:
                continue
            text = str(item).strip().lower()
            if text in SOURCE_PRIORITY:
                out.add(text)
    return out


def _normalize_core_field(field: str, value):
    if value in (None, ""):
        return None
    if field in {"survey_start_date", "survey_end_date"}:
        norm = _norm_date(value)
        return norm or None
    if field == "sample_size":
        try:
            return int(value)
        except (TypeError, ValueError):
            return _norm_text(value) or None
    if field == "region_code":
        return _norm_text(value).replace(" ", "").upper() or None
    if field == "office_type":
        return _norm_text(value) or None
    return _norm_text(value) or None


def _normalize_source_grade(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().upper()
    return text or None


def _merge_source_grade(existing_grade, incoming_grade):
    e = _normalize_source_grade(existing_grade)
    i = _normalize_source_grade(incoming_grade)
    if e is None:
        return i
    if i is None:
        return e
    e_score = SOURCE_GRADE_PRIORITY.get(e, -1)
    i_score = SOURCE_GRADE_PRIORITY.get(i, -1)
    if i_score > e_score:
        return i
    if e_score > i_score:
        return e
    return i


def merge_observation_by_priority(existing: dict, incoming: dict) -> dict:
    existing_source = (existing.get("source_channel") or "article").lower()
    incoming_source = (incoming.get("source_channel") or "article").lower()
    existing_pri = SOURCE_PRIORITY.get(existing_source, 1)
    incoming_pri = SOURCE_PRIORITY.get(incoming_source, 1)

    core_conflicts: list[str] = []
    for field in ("region_code", "office_type", "survey_start_date", "survey_end_date", "sample_size", "poll_block_id"):
        old = _normalize_core_field(field, existing.get(field))
        new = _normalize_core_field(field, incoming.get(field))
        if old is not None and new is not None and old != new:
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
        "confidence_level",
        "sample_size",
        "response_rate",
        "margin_of_error",
        "region_code",
        "office_type",
        "matchup_id",
        "poll_block_id",
        "audience_scope",
        "audience_region_code",
        "sampling_population_text",
        "legal_completeness_score",
        "legal_filled_count",
        "legal_required_count",
        "date_resolution",
        "date_inference_mode",
        "date_inference_confidence",
        "official_release_at",
        "method",
    )
    for field in meta_fields:
        existing_value = existing.get(field)
        incoming_value = incoming.get(field)
        primary = incoming_value if incoming_wins else existing_value
        secondary = existing_value if incoming_wins else incoming_value
        merged[field] = primary if primary not in (None, "") else secondary

    channels = _normalize_channels(existing.get("source_channels"))
    channels.update(_normalize_channels(incoming.get("source_channels")))
    channels.update(_normalize_channels(existing_source))
    channels.update(_normalize_channels(incoming_source))
    ordered_channels = [channel for channel in ("article", "nesdc") if channel in channels]

    merged["source_channel"] = "nesdc" if "nesdc" in ordered_channels else "article"
    merged["source_channels"] = ordered_channels or None
    merged["poll_fingerprint"] = incoming.get("poll_fingerprint") or existing.get("poll_fingerprint")
    merged["observation_key"] = existing.get("observation_key") or incoming.get("observation_key")
    merged["verified"] = bool(existing.get("verified")) or bool(incoming.get("verified"))
    merged["source_grade"] = _merge_source_grade(existing.get("source_grade"), incoming.get("source_grade"))
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
