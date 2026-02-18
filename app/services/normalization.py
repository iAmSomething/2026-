import re
from typing import NamedTuple


class NormalizedValue(NamedTuple):
    value_min: float | None
    value_max: float | None
    value_mid: float | None
    is_missing: bool


SINGLE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*$")
RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[~\-]\s*(\d+(?:\.\d+)?)\s*%?\s*$")
BAND_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*대\s*$")


def normalize_percentage(raw: str | None) -> NormalizedValue:
    if raw is None:
        return NormalizedValue(None, None, None, True)

    raw = raw.strip()
    if not raw or raw in {"언급 없음", "미공개", "N/A", "-"}:
        return NormalizedValue(None, None, None, True)

    matched = RANGE_RE.match(raw)
    if matched:
        lo, hi = float(matched.group(1)), float(matched.group(2))
        lo, hi = min(lo, hi), max(lo, hi)
        return NormalizedValue(lo, hi, (lo + hi) / 2.0, False)

    matched = BAND_RE.match(raw)
    if matched:
        base = float(matched.group(1))
        lo = base
        hi = base + 9
        return NormalizedValue(lo, hi, (lo + hi) / 2.0, False)

    matched = SINGLE_RE.match(raw)
    if matched:
        val = float(matched.group(1))
        return NormalizedValue(val, val, val, False)

    return NormalizedValue(None, None, None, True)
