from __future__ import annotations

import re
from dataclasses import dataclass

LEGACY_REGION_PREFIX_MAP = {
    # 강원도(legacy 32) -> 강원특별자치도(42)
    "32": "42",
}

_SIMPLE_REGION_CODE_RE = re.compile(r"^\d{2}(?:-\d{3})?$")
_COMPACT_REGION_CODE_RE = re.compile(r"^\d{5}$")
_SCENARIO_REGION_CODE_RE = re.compile(r"^\d{2}-\d{2}-\d{3}$")


@dataclass(frozen=True)
class RegionCodeNormalization:
    raw: str
    canonical: str | None
    is_code_like: bool
    was_aliased: bool


def _strip_country_prefix(value: str) -> str:
    if value.startswith("KR-"):
        return value[3:]
    if value.startswith("KR"):
        return value[2:]
    return value


def _apply_legacy_prefix_alias(code: str) -> str:
    prefix = code[:2]
    mapped_prefix = LEGACY_REGION_PREFIX_MAP.get(prefix, prefix)
    return f"{mapped_prefix}{code[2:]}"


def _canonicalize_normalized_token(normalized_token: str) -> str | None:
    stripped = _strip_country_prefix(normalized_token)
    if _SCENARIO_REGION_CODE_RE.fullmatch(stripped):
        return _apply_legacy_prefix_alias(stripped)
    if _SIMPLE_REGION_CODE_RE.fullmatch(stripped):
        digits = "".join(ch for ch in stripped if ch.isdigit())
        if len(digits) == 2:
            return _apply_legacy_prefix_alias(f"{digits}-000")
        if len(digits) == 5:
            return _apply_legacy_prefix_alias(f"{digits[:2]}-{digits[2:]}")
    if _COMPACT_REGION_CODE_RE.fullmatch(stripped):
        return _apply_legacy_prefix_alias(f"{stripped[:2]}-{stripped[2:]}")
    return None


def normalize_region_code_input(raw_value: str | None) -> RegionCodeNormalization:
    raw = (raw_value or "").strip()
    if not raw:
        return RegionCodeNormalization(raw=raw, canonical=None, is_code_like=False, was_aliased=False)

    normalized_token = raw.replace(" ", "").replace("_", "-").upper()
    canonical = _canonicalize_normalized_token(normalized_token)
    if canonical is None:
        return RegionCodeNormalization(raw=raw, canonical=None, is_code_like=False, was_aliased=False)

    was_aliased = normalized_token != canonical
    return RegionCodeNormalization(raw=raw, canonical=canonical, is_code_like=True, was_aliased=was_aliased)
