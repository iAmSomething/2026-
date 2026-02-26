from __future__ import annotations

import re
from typing import Any

ALLOWED_PARTY_INFERENCE_SOURCES = {"name_rule", "article_context", "manual"}
TRUE_TOKENS = {"1", "true", "yes", "y", "on"}
FALSE_TOKENS = {"0", "false", "no", "n", "off"}
MISSING_TOKENS = {"", "-", "na", "n/a", "none", "null", "미기재", "미상", "unknown"}
PRESIDENT_JOB_APPROVAL_KEYWORDS = (
    "대통령",
    "국정수행",
    "국정평가",
    "직무",
    "긍정",
    "부정",
    "잘한다",
    "잘못",
    "못한다",
)
ELECTION_FRAME_KEYWORDS = (
    "선거성격",
    "국정안정",
    "국정견제",
    "안정론",
    "견제론",
    "정부견제",
    "여당힘",
    "야당견제",
    "정권교체",
    "정권재창출",
    "정권심판",
)
AUDIENCE_SCOPE_ALIASES = {
    "national": "national",
    "nation": "national",
    "nationwide": "national",
    "전국": "national",
    "전체": "national",
    "regional": "regional",
    "region": "regional",
    "광역": "regional",
    "시도": "regional",
    "시/도": "regional",
    "local": "local",
    "sigungu": "local",
    "시군구": "local",
    "기초": "local",
}


def _normalized_option_text(*parts: Any) -> str:
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, str):
            continue
        token = re.sub(r"\s+", "", part.strip().lower())
        if token:
            chunks.append(token)
    return " ".join(chunks)


def normalize_option_type(
    option_type: Any,
    option_name: Any,
    *,
    question_text: Any = None,
) -> tuple[str, bool, str | None]:
    normalized_type = str(option_type or "").strip().lower()
    if normalized_type == "candidate":
        return "candidate", False, None
    if normalized_type in {"candidate_matchup", "party_support", "president_job_approval", "election_frame"}:
        return normalized_type, False, None
    if normalized_type != "presidential_approval":
        return normalized_type, False, None

    normalized_text = _normalized_option_text(option_name, question_text)
    has_job_approval_signal = any(keyword in normalized_text for keyword in PRESIDENT_JOB_APPROVAL_KEYWORDS)
    has_election_frame_signal = any(keyword in normalized_text for keyword in ELECTION_FRAME_KEYWORDS)

    if has_job_approval_signal and not has_election_frame_signal:
        return "president_job_approval", False, None
    if has_election_frame_signal and not has_job_approval_signal:
        return "election_frame", False, None
    if has_job_approval_signal and has_election_frame_signal:
        return "presidential_approval", True, "AMBIGUOUS_OPTION_TYPE_SIGNAL"
    return "presidential_approval", True, "UNCLASSIFIED_PRESIDENTIAL_OPTION"


def _normalize_party_inferred(value: Any, party_name: str | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in TRUE_TOKENS:
            return True
        if token in FALSE_TOKENS or token == "":
            return False
        return True
    if isinstance(party_name, str) and party_name.strip():
        return True
    return False


def _normalize_party_inference_source(source: Any, party_inferred: bool) -> str | None:
    if isinstance(source, str):
        normalized = source.strip().lower()
        if normalized in ALLOWED_PARTY_INFERENCE_SOURCES:
            return normalized
    return "manual" if party_inferred else None


def _normalize_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        token = value.strip().lower().replace(",", "")
        if token in MISSING_TOKENS:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", token)
        if not match:
            return None
        return abs(float(match.group(0)))
    return None


def _normalize_audience_scope(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in AUDIENCE_SCOPE_ALIASES:
        return AUDIENCE_SCOPE_ALIASES[lowered]
    if raw in AUDIENCE_SCOPE_ALIASES:
        return AUDIENCE_SCOPE_ALIASES[raw]
    return None


def _normalized_region_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def normalize_candidate_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    party_name_raw = candidate.get("party_name")
    party_name = party_name_raw.strip() if isinstance(party_name_raw, str) else party_name_raw
    if isinstance(party_name, str) and not party_name:
        party_name = None
    candidate["party_name"] = party_name
    original_inferred = candidate.get("party_inferred")
    normalized_bool = _normalize_party_inferred(original_inferred, party_name)
    candidate["party_inferred"] = normalized_bool

    if (
        normalized_bool
        and (not isinstance(party_name, str) or not party_name.strip())
        and isinstance(original_inferred, str)
        and original_inferred.strip().lower() not in TRUE_TOKENS | FALSE_TOKENS
    ):
        candidate["party_name"] = original_inferred.strip()

    candidate["party_inference_source"] = _normalize_party_inference_source(
        candidate.get("party_inference_source"), normalized_bool
    )

    return candidate


def normalize_option_fields(option: dict[str, Any]) -> dict[str, Any]:
    normalized_option_type, needs_manual_review, reason = normalize_option_type(
        option.get("option_type"),
        option.get("option_name"),
        question_text=option.get("question_text") or option.get("evidence_text"),
    )
    option["option_type"] = normalized_option_type
    if needs_manual_review:
        option["needs_manual_review"] = True
        option["manual_review_reason"] = reason

    option_name = option.get("option_name")
    inferred = _normalize_party_inferred(option.get("party_inferred"), option_name)
    option["party_inferred"] = inferred
    option["party_inference_source"] = _normalize_party_inference_source(option.get("party_inference_source"), inferred)
    return option


def normalize_observation_fields(observation: dict[str, Any]) -> dict[str, Any]:
    scope = _normalize_audience_scope(observation.get("audience_scope"))
    observation["audience_scope"] = scope

    region_code = _normalized_region_code(observation.get("region_code"))
    audience_region_code = _normalized_region_code(observation.get("audience_region_code"))
    if scope == "national":
        audience_region_code = None
    elif scope in {"regional", "local"} and audience_region_code is None:
        audience_region_code = region_code
    observation["audience_region_code"] = audience_region_code

    observation["margin_of_error"] = _normalize_float(observation.get("margin_of_error"))
    return observation


def normalize_ingest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for record in payload.get("records") or []:
        observation = record.get("observation")
        if isinstance(observation, dict):
            normalize_observation_fields(observation)
        for candidate in record.get("candidates") or []:
            if isinstance(candidate, dict):
                normalize_candidate_fields(candidate)
        for option in record.get("options") or []:
            if isinstance(option, dict):
                normalize_option_fields(option)
    return payload
