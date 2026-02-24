from __future__ import annotations

import re
from typing import Any

ALLOWED_PARTY_INFERENCE_SOURCES = {"name_rule", "article_context", "manual"}
TRUE_TOKENS = {"1", "true", "yes", "y", "on"}
FALSE_TOKENS = {"0", "false", "no", "n", "off"}
MISSING_TOKENS = {"", "-", "na", "n/a", "none", "null", "미기재", "미상", "unknown"}
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
