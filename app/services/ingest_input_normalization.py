from __future__ import annotations

from typing import Any

ALLOWED_PARTY_INFERENCE_SOURCES = {"name_rule", "article_context", "manual"}
TRUE_TOKENS = {"1", "true", "yes", "y", "on"}
FALSE_TOKENS = {"0", "false", "no", "n", "off"}


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


def normalize_candidate_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    party_name = candidate.get("party_name")
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

    source = candidate.get("party_inference_source")
    if source not in ALLOWED_PARTY_INFERENCE_SOURCES:
        candidate["party_inference_source"] = "manual" if normalized_bool else None

    return candidate


def normalize_ingest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for record in payload.get("records") or []:
        for candidate in record.get("candidates") or []:
            if isinstance(candidate, dict):
                normalize_candidate_fields(candidate)
    return payload
