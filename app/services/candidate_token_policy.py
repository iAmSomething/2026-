from __future__ import annotations

import re
from typing import Iterable

DEFAULT_CANDIDATE_NAME_PATTERN = re.compile(r"^[가-힣]{2,8}$")

_NOISE_EXACT_TOKENS = {
    "오차는",
    "응답률은",
    "지지율은",
    "오차범위",
    "표본오차",
    "응답률",
    "조사기관",
    "여론조사",
    "지지율",
    "민주",
    "민주당",
    "더불어민주당",
    "국힘",
    "국민의힘",
    "차이",
    "같은",
    "외",
    "지지",
    "지지도",
    "재정자립도",
    "적합도",
    "선호도",
    "인지도",
    "호감도",
    "비호감도",
    "국정안정론",
    "국정견제론",
    "정권교체",
    "정권재창출",
    "정권심판",
    "정권지원",
    "긍정평가",
    "부정평가",
    "전라",
    "경상",
    "충청",
}

_NOISE_SUBSTRING_TOKENS = {
    "오차",
    "오차범위",
    "표본오차",
    "응답률",
    "조사기관",
    "여론조사",
    "지지율",
    "지지도",
    "지지",
    "재정자립",
    "적합도",
    "선호도",
    "안정론",
    "견제론",
    "정권",
    "긍정평가",
    "부정평가",
    "더불어민주당",
    "국민의힘",
    "전라",
    "경상",
    "충청",
}

_POSTPOSITION_SUFFIXES = (
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "와",
    "과",
    "의",
    "도",
    "만",
    "로",
    "에",
)


def normalize_candidate_token(value: str | None) -> str:
    token = re.sub(r"\s+", "", str(value or "").strip().lower())
    return re.sub(r"[^0-9a-z가-힣]", "", token)


def _token_variants(token: str) -> set[str]:
    variants = {token}
    for suffix in _POSTPOSITION_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            variants.add(token[: -len(suffix)])
    return variants


def is_noise_candidate_token(
    option_name: str | None,
    *,
    name_pattern: re.Pattern[str] = DEFAULT_CANDIDATE_NAME_PATTERN,
    extra_exact_tokens: Iterable[str] = (),
    extra_substring_tokens: Iterable[str] = (),
) -> bool:
    raw = str(option_name or "")
    token = normalize_candidate_token(raw)
    if not token:
        return True

    variants = _token_variants(token)
    exact_tokens = _NOISE_EXACT_TOKENS | {normalize_candidate_token(x) for x in extra_exact_tokens}
    if any(v in exact_tokens for v in variants):
        return True

    substring_tokens = _NOISE_SUBSTRING_TOKENS | {normalize_candidate_token(x) for x in extra_substring_tokens}
    for v in variants:
        if any(part and part in v for part in substring_tokens):
            return True

    if any(ch.isdigit() for ch in token):
        return True
    if "%" in raw:
        return True
    if name_pattern.fullmatch(token) is None:
        return True
    return False
