from collections import Counter
from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.models.schemas import IngestPayload, PollOptionInput
from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
    SURVEY_END_DATE_CUTOFF,
    has_article_source,
    parse_datetime_like,
    published_at_cutoff_reason,
    survey_end_date_cutoff_reason,
)
from app.services.candidate_token_policy import is_noise_candidate_token
from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService
from app.services.errors import DuplicateConflictError
from app.services.fingerprint import build_poll_fingerprint
from app.services.ingest_input_normalization import normalize_option_type
from app.services.normalization import normalize_percentage
from app.services.region_code_normalizer import normalize_region_code_input

PARTY_INFERENCE_REVIEW_THRESHOLD = 0.8
PARTY_INFERENCE_SOURCE_OFFICIAL_REGISTRY_V3 = "official_registry_v3"
PARTY_INFERENCE_SOURCE_INCUMBENT_CONTEXT_V3 = "incumbent_context_v3"
SCENARIO_NAME_RE = re.compile(r"[가-힣]{2,6}")
SCENARIO_H2H_PAIR_RE = re.compile(
    r"([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?\s*[-~]\s*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?"
)
SCENARIO_MULTI_SINGLE_RE = re.compile(r"다자대결[^가-힣0-9%]*([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?")
SCENARIO_MULTI_ITEM_RE = re.compile(r"([가-힣]{2,6})\s*([0-9]{1,2}(?:\.[0-9]+)?)\s*%?")
DEFAULT_SG_TYPECODES = ("3", "4", "5")
OFFICE_TYPE_TO_SG_TYPECODES = {
    "광역자치단체장": ("3", "4"),
    "기초자치단체장": ("4", "3", "5"),
}
CANDIDATE_PROFILE_FIELDS = (
    "party_name",
    "gender",
    "birth_date",
    "job",
    "career_summary",
    "election_history",
)
CANDIDATE_PROFILE_REQUIRED_FOR_REVIEW = (
    "party_name",
    "career_summary",
    "election_history",
)
SCOPE_INFERENCE_CONFLICT_THRESHOLD = 0.8
SCOPE_INFERENCE_LOW_CONFIDENCE_THRESHOLD = 0.75
POPULATION_CODE_RE = re.compile(r"\b(?:(?:KR-?)?\d{2}(?:-\d{3})?|\d{5})\b", re.IGNORECASE)
SCOPE_NATIONAL_TOKENS = (
    "전국",
    "전국민",
    "전국거주",
    "대한민국",
)
SCOPE_REGIONAL_HINT_TOKENS = (
    "광역",
    "특별시",
    "광역시",
    "특별자치시",
    "특별자치도",
    "도거주",
    "시도",
)
SCOPE_LOCAL_HINT_TOKENS = (
    "시군구",
    "구거주",
    "군거주",
    "읍면동",
    "동거주",
)
POPULATION_REGION_ALIAS_TO_CODE = {
    "서울특별시": "11-000",
    "서울시": "11-000",
    "서울": "11-000",
    "부산광역시": "26-000",
    "부산시": "26-000",
    "부산": "26-000",
    "대구광역시": "27-000",
    "대구시": "27-000",
    "대구": "27-000",
    "인천광역시": "28-000",
    "인천시": "28-000",
    "인천": "28-000",
    "광주광역시": "29-000",
    "광주시": "29-000",
    "광주": "29-000",
    "대전광역시": "30-000",
    "대전시": "30-000",
    "대전": "30-000",
    "울산광역시": "31-000",
    "울산시": "31-000",
    "울산": "31-000",
    "세종특별자치시": "36-000",
    "세종시": "36-000",
    "세종": "36-000",
    "경기도": "41-000",
    "경기": "41-000",
    "강원특별자치도": "42-000",
    "강원도": "42-000",
    "강원": "42-000",
    "충청북도": "43-000",
    "충북": "43-000",
    "충청남도": "44-000",
    "충남": "44-000",
    "전북특별자치도": "45-000",
    "전라북도": "45-000",
    "전북": "45-000",
    "전라남도": "46-000",
    "전남": "46-000",
    "경상북도": "47-000",
    "경북": "47-000",
    "경상남도": "48-000",
    "경남": "48-000",
    "제주특별자치도": "50-000",
    "제주도": "50-000",
    "제주": "50-000",
    "강남구": "11-680",
    "송파구": "11-710",
    "서초구": "11-650",
    "기장군": "26-710",
    "해운대구": "26-350",
    "연수구": "28-450",
    "춘천시": "42-110",
    "청주시": "43-110",
    "천안시": "44-130",
    "전주시": "45-110",
    "목포시": "46-110",
    "포항시": "47-110",
    "창원시": "48-110",
    "제주시": "50-110",
    "서귀포시": "50-130",
}
SORTED_POPULATION_REGION_ALIASES = sorted(
    POPULATION_REGION_ALIAS_TO_CODE.items(),
    key=lambda item: len(item[0]),
    reverse=True,
)
SURVEY_NAME_OFFICE_RE = re.compile(r"([가-힣]{2,10})(시장|도지사|지사|교육감)")

SCOPE_HARDGUARD_OFFICE_TYPE = "광역자치단체장"
SCOPE_HARDGUARD_NEEDLES: tuple[tuple[str, str], ...] = (
    ("서울시장", "11-000"),
    ("부산시장", "26-000"),
    ("대구시장", "27-000"),
    ("인천시장", "28-000"),
    ("광주시장", "29-000"),
    ("대전시장", "30-000"),
    ("울산시장", "31-000"),
    ("세종시장", "36-000"),
    ("경기도지사", "41-000"),
    ("경기지사", "41-000"),
    ("강원특별자치도지사", "42-000"),
    ("강원도지사", "42-000"),
    ("강원지사", "42-000"),
    ("충청북도지사", "43-000"),
    ("충북지사", "43-000"),
    ("충청남도지사", "44-000"),
    ("충남지사", "44-000"),
    ("전북특별자치도지사", "45-000"),
    ("전라북도지사", "45-000"),
    ("전북지사", "45-000"),
    ("전라남도지사", "46-000"),
    ("전남지사", "46-000"),
    ("경상북도지사", "47-000"),
    ("경북지사", "47-000"),
    ("경상남도지사", "48-000"),
    ("경남지사", "48-000"),
    ("제주특별자치도지사", "50-000"),
    ("제주도지사", "50-000"),
    ("제주지사", "50-000"),
)
SCOPE_HARDGUARD_SIDO_NAME_BY_CODE = {
    "11-000": "서울특별시",
    "26-000": "부산광역시",
    "27-000": "대구광역시",
    "28-000": "인천광역시",
    "29-000": "광주광역시",
    "30-000": "대전광역시",
    "31-000": "울산광역시",
    "36-000": "세종특별자치시",
    "41-000": "경기도",
    "42-000": "강원특별자치도",
    "43-000": "충청북도",
    "44-000": "충청남도",
    "45-000": "전북특별자치도",
    "46-000": "전라남도",
    "47-000": "경상북도",
    "48-000": "경상남도",
    "50-000": "제주특별자치도",
}

LOGGER = logging.getLogger(__name__)


@dataclass
class IngestResult:
    run_id: int
    processed_count: int
    error_count: int
    status: str


@dataclass
class ScopeInferenceResolution:
    scope: str | None
    audience_region_code: str | None
    inferred_scope: str | None
    inferred_region_code: str | None
    confidence: float
    hard_fail_reason: str | None
    low_confidence_reason: str | None


def _infer_election_id(matchup_id: str) -> str:
    if "|" in matchup_id:
        return matchup_id.split("|", 1)[0]
    if ":" in matchup_id:
        return matchup_id.split(":", 1)[0]
    return "unknown"


def _office_region_from_survey_name(survey_name: str) -> tuple[str, str] | None:
    text = str(survey_name or "").strip()
    if not text:
        return None

    for match in SURVEY_NAME_OFFICE_RE.finditer(text):
        prefix = match.group(1).strip()
        office_token = match.group(2)
        if not prefix:
            continue

        alias_candidates: list[str] = [prefix]
        if office_token == "시장":
            alias_candidates = [f"{prefix}광역시", f"{prefix}시", prefix]
        elif office_token in {"지사", "도지사"}:
            alias_candidates = [f"{prefix}도", f"{prefix}특별자치도", prefix]
        elif office_token == "교육감":
            alias_candidates = [
                f"{prefix}광역시",
                f"{prefix}특별시",
                f"{prefix}특별자치시",
                f"{prefix}도",
                f"{prefix}특별자치도",
                prefix,
            ]

        region_code = None
        for alias in alias_candidates:
            normalized_alias = alias.strip()
            if not normalized_alias:
                continue
            mapped = POPULATION_REGION_ALIAS_TO_CODE.get(normalized_alias)
            if mapped:
                region_code = mapped
                break
        if region_code is None:
            continue

        if office_token == "시장":
            office_type = "광역자치단체장" if region_code.endswith("-000") else "기초자치단체장"
            return region_code, office_type
        if office_token in {"지사", "도지사"}:
            return _to_sido_region_code(region_code) or region_code, "광역자치단체장"
        if office_token == "교육감":
            return _to_sido_region_code(region_code) or region_code, "교육감"
    return None


def _apply_survey_name_matchup_correction(
    *,
    observation_payload: dict[str, Any],
    article_title: str | None,
) -> None:
    survey_name = str(observation_payload.get("survey_name") or "").strip()
    title_text = str(article_title or "").strip()
    inferred = _office_region_from_survey_name(f"{survey_name} {title_text}".strip())
    if not inferred:
        return

    region_code, office_type = inferred
    election_id = _infer_election_id(str(observation_payload.get("matchup_id") or "2026_local"))
    observation_payload["region_code"] = region_code
    observation_payload["office_type"] = office_type
    observation_payload["matchup_id"] = f"{election_id}|{office_type}|{region_code}"

    current_scope = observation_payload.get("audience_scope")
    if current_scope not in {"national", "regional", "local"}:
        observation_payload["audience_scope"] = "regional" if region_code.endswith("-000") else "local"


def _normalize_region_code(value: Any) -> str | None:
    if value is None:
        return None
    normalized = normalize_region_code_input(str(value))
    if normalized.canonical:
        return normalized.canonical
    raw = str(value).strip()
    return raw or None


def _rebuild_matchup_id(matchup_id: str, office_type: str, region_code: str) -> str:
    return f"{_infer_election_id(matchup_id)}|{office_type}|{region_code}"


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _resolve_scope_hardguard_region_code(*texts: Any) -> tuple[str, str] | None:
    compact = "".join(_compact_text(text) for text in texts if text)
    if not compact:
        return None
    for needle, region_code in SCOPE_HARDGUARD_NEEDLES:
        if needle in compact:
            return region_code, needle
    return None


def _apply_scope_hardguard(record) -> tuple[bool, str | None]:
    resolved = _resolve_scope_hardguard_region_code(
        record.article.title,
        record.article.raw_text,
        record.observation.survey_name,
    )
    if resolved is None:
        return False, None

    region_code, needle = resolved
    changed = False
    if record.observation.office_type != SCOPE_HARDGUARD_OFFICE_TYPE:
        record.observation.office_type = SCOPE_HARDGUARD_OFFICE_TYPE
        changed = True
    if _normalize_region_code(record.observation.region_code) != region_code:
        record.observation.region_code = region_code
        changed = True
    rebuilt_matchup_id = _rebuild_matchup_id(
        matchup_id=record.observation.matchup_id,
        office_type=SCOPE_HARDGUARD_OFFICE_TYPE,
        region_code=region_code,
    )
    if record.observation.matchup_id != rebuilt_matchup_id:
        record.observation.matchup_id = rebuilt_matchup_id
        changed = True

    if record.region is not None:
        if _normalize_region_code(record.region.region_code) != region_code:
            record.region.region_code = region_code
            changed = True
        target_sido_name = SCOPE_HARDGUARD_SIDO_NAME_BY_CODE.get(region_code)
        if target_sido_name and record.region.sido_name != target_sido_name:
            record.region.sido_name = target_sido_name
            changed = True
        if record.region.sigungu_name != "전체":
            record.region.sigungu_name = "전체"
            changed = True
        if record.region.admin_level != "sido":
            record.region.admin_level = "sido"
            changed = True
        if record.region.parent_region_code is not None:
            record.region.parent_region_code = None
            changed = True

    return changed, needle


def _to_sido_region_code(region_code: str | None) -> str | None:
    normalized = _normalize_region_code(region_code)
    if not normalized:
        return None
    if len(normalized) >= 2:
        return f"{normalized[:2]}-000"
    return normalized


def _normalize_population_text(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        return "", ""
    raw = " ".join(value.strip().split())
    compact = re.sub(r"\s+", "", raw)
    return raw, compact


def _infer_population_region_code(population_text: str, compact_text: str) -> str | None:
    if not population_text and not compact_text:
        return None

    explicit_match = POPULATION_CODE_RE.search(population_text)
    if explicit_match:
        explicit_code = _normalize_region_code(explicit_match.group(0))
        if explicit_code:
            return explicit_code

    for alias, code in SORTED_POPULATION_REGION_ALIASES:
        if alias in population_text or alias in compact_text:
            return code
    return None


def _infer_scope_from_sampling_population(
    *,
    sampling_population_text: Any,
) -> tuple[str | None, str | None, float]:
    population_text, compact_text = _normalize_population_text(sampling_population_text)
    if not population_text and not compact_text:
        return None, None, 0.0

    scores = {"national": 0.0, "regional": 0.0, "local": 0.0}
    if any(token in compact_text for token in SCOPE_NATIONAL_TOKENS):
        scores["national"] += 3.0
    if any(token in compact_text for token in SCOPE_REGIONAL_HINT_TOKENS):
        scores["regional"] += 1.0
    if any(token in compact_text for token in SCOPE_LOCAL_HINT_TOKENS):
        scores["local"] += 1.0

    inferred_region_code = _infer_population_region_code(population_text, compact_text)
    if inferred_region_code:
        if inferred_region_code.endswith("-000"):
            scores["regional"] += 2.0
        else:
            scores["local"] += 2.0

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_scope, top_score = ordered[0]
    second_score = ordered[1][1]
    if top_score <= 0:
        return None, inferred_region_code, 0.0
    if top_score == second_score:
        return None, inferred_region_code, 0.6
    confidence = 0.92 if top_score - second_score >= 2 else 0.8
    return top_scope, inferred_region_code, confidence


def _resolve_observation_scope(observation_payload: dict[str, Any]) -> ScopeInferenceResolution:
    explicit_scope = observation_payload.get("audience_scope")
    explicit_region_code = _normalize_region_code(observation_payload.get("audience_region_code"))
    observation_region_code = _normalize_region_code(observation_payload.get("region_code"))

    inferred_scope, inferred_region_code, confidence = _infer_scope_from_sampling_population(
        sampling_population_text=observation_payload.get("sampling_population_text")
    )

    if (
        explicit_scope in {"national", "regional", "local"}
        and inferred_scope in {"national", "regional", "local"}
        and explicit_scope != inferred_scope
        and confidence >= SCOPE_INFERENCE_CONFLICT_THRESHOLD
    ):
        return ScopeInferenceResolution(
            scope=explicit_scope,
            audience_region_code=explicit_region_code,
            inferred_scope=inferred_scope,
            inferred_region_code=inferred_region_code,
            confidence=confidence,
            hard_fail_reason=(
                "AUDIENCE_SCOPE_CONFLICT_POPULATION "
                f"declared={explicit_scope} inferred={inferred_scope} "
                f"confidence={confidence:.2f} sampling_population={observation_payload.get('sampling_population_text')}"
            ),
            low_confidence_reason=None,
        )

    final_scope = explicit_scope if explicit_scope in {"national", "regional", "local"} else inferred_scope
    if final_scope is None and observation_region_code:
        final_scope = "regional" if observation_region_code.endswith("-000") else "local"

    final_region_code = explicit_region_code
    if final_scope == "national":
        final_region_code = None
    elif final_scope in {"regional", "local"}:
        if final_region_code is None and inferred_region_code:
            final_region_code = inferred_region_code
        if final_region_code is None:
            final_region_code = observation_region_code

        if final_scope == "regional":
            final_region_code = _to_sido_region_code(final_region_code)
        elif final_scope == "local" and final_region_code and final_region_code.endswith("-000"):
            if observation_region_code and not observation_region_code.endswith("-000"):
                final_region_code = observation_region_code

    region_conflict = False
    if final_scope == "regional" and explicit_region_code and inferred_region_code:
        region_conflict = _to_sido_region_code(explicit_region_code) != _to_sido_region_code(inferred_region_code)
    elif final_scope == "local" and explicit_region_code and inferred_region_code:
        region_conflict = _normalize_region_code(explicit_region_code) != _normalize_region_code(inferred_region_code)

    if region_conflict and confidence >= SCOPE_INFERENCE_CONFLICT_THRESHOLD:
        return ScopeInferenceResolution(
            scope=final_scope,
            audience_region_code=final_region_code,
            inferred_scope=inferred_scope,
            inferred_region_code=inferred_region_code,
            confidence=confidence,
            hard_fail_reason=(
                "AUDIENCE_SCOPE_CONFLICT_REGION "
                f"declared_region={explicit_region_code} inferred_region={inferred_region_code} "
                f"scope={final_scope} confidence={confidence:.2f}"
            ),
            low_confidence_reason=None,
        )

    low_confidence_reason = None
    if (
        inferred_scope is not None
        and confidence < SCOPE_INFERENCE_LOW_CONFIDENCE_THRESHOLD
        and explicit_scope not in {"national", "regional", "local"}
    ):
        low_confidence_reason = (
            "AUDIENCE_SCOPE_LOW_CONFIDENCE "
            f"inferred={inferred_scope} confidence={confidence:.2f} "
            f"sampling_population={observation_payload.get('sampling_population_text')}"
        )

    return ScopeInferenceResolution(
        scope=final_scope,
        audience_region_code=final_region_code,
        inferred_scope=inferred_scope,
        inferred_region_code=inferred_region_code,
        confidence=confidence,
        hard_fail_reason=None,
        low_confidence_reason=low_confidence_reason,
    )


def _office_type_sg_types(office_type: str | None) -> tuple[str, ...]:
    return OFFICE_TYPE_TO_SG_TYPECODES.get(office_type or "", DEFAULT_SG_TYPECODES)


def _normalize_candidate_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    return text


def _looks_like_noise_candidate(option_name: str) -> bool:
    return is_noise_candidate_token(option_name)


def _candidate_verify_matched_key(
    *,
    source: str,
    normalized_name: str,
    candidate_id: str | None,
) -> str:
    if candidate_id:
        return f"{source}:{candidate_id}"
    if normalized_name:
        return f"{source}:{normalized_name}"
    return source


def _normalize_party_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _encode_party_inference_evidence(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _apply_party_inference_v3(
    *,
    option_payload: dict[str, Any],
    record,
    candidate_party_counter_map: dict[str, Counter[str]],
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> None:
    option_type = option_payload.get("option_type")
    if option_type not in {"candidate", "candidate_matchup"}:
        return

    option_name = str(option_payload.get("option_name") or "").strip()
    if not option_name or _looks_like_noise_candidate(option_name):
        return

    existing_party = _normalize_party_name(option_payload.get("party_name"))
    if existing_party:
        option_payload["party_name"] = existing_party
        if option_payload.get("party_inferred") and option_payload.get("party_inference_evidence") in (None, ""):
            option_payload["party_inference_evidence"] = _encode_party_inference_evidence(
                {
                    "method": "party_inference_v3",
                    "rule": "prepopulated_party_name",
                    "party_name": existing_party,
                }
            )
        return

    normalized_name = _normalize_candidate_token(option_name)
    if not normalized_name:
        return

    context_counter = candidate_party_counter_map.get(normalized_name)
    if context_counter:
        top_party, top_count = context_counter.most_common(1)[0]
        total = int(sum(context_counter.values()))
        ratio = float(top_count) / float(max(1, total))
        if total == 1:
            confidence = 0.93
            source = PARTY_INFERENCE_SOURCE_OFFICIAL_REGISTRY_V3
        else:
            confidence = round(max(0.55, min(0.95, ratio)), 3)
            source = PARTY_INFERENCE_SOURCE_INCUMBENT_CONTEXT_V3

        option_payload["party_name"] = top_party
        option_payload["party_inferred"] = True
        option_payload["party_inference_source"] = source
        option_payload["party_inference_confidence"] = confidence
        option_payload["party_inference_evidence"] = _encode_party_inference_evidence(
            {
                "method": "party_inference_v3",
                "rule": "candidate_context_counter",
                "candidate_name": option_name,
                "selected_party": top_party,
                "candidate_party_counter": dict(context_counter),
                "selected_count": top_count,
                "total_count": total,
                "support_ratio": round(ratio, 4),
            }
        )
        if confidence < PARTY_INFERENCE_REVIEW_THRESHOLD:
            option_payload["needs_manual_review"] = True
        return

    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        service = _build_or_get_candidate_service(
            record=record,
            sg_typecode=sg_typecode,
            service_cache=service_cache,
        )
        if service is None:
            continue
        enriched = service.enrich_candidate({"name_ko": option_name, "party_name": None})
        inferred_party = _normalize_party_name(enriched.get("party_name"))
        if not inferred_party:
            continue

        confidence = 0.88
        option_payload["party_name"] = inferred_party
        option_payload["party_inferred"] = True
        option_payload["party_inference_source"] = PARTY_INFERENCE_SOURCE_OFFICIAL_REGISTRY_V3
        option_payload["party_inference_confidence"] = confidence
        option_payload["party_inference_evidence"] = _encode_party_inference_evidence(
            {
                "method": "party_inference_v3",
                "rule": "data_go_enrich_lookup",
                "candidate_name": option_name,
                "selected_party": inferred_party,
                "sg_typecode": sg_typecode,
            }
        )
        if confidence < PARTY_INFERENCE_REVIEW_THRESHOLD:
            option_payload["needs_manual_review"] = True
        return


def _resolve_region_names(record) -> tuple[str | None, str | None]:
    region = getattr(record, "region", None)
    if region is None:
        return None, None
    sd_name = getattr(region, "sido_name", None)
    sgg_name = getattr(region, "sigungu_name", None)
    if sgg_name == "전체":
        sgg_name = None
    return sd_name, sgg_name


def _build_candidate_service(
    *,
    record,
    sg_typecode: str,
) -> DataGoCandidateService | None:
    try:
        settings = get_settings()
    except Exception:  # noqa: BLE001
        return None

    election_id = _infer_election_id(record.observation.matchup_id)
    sd_name, sgg_name = _resolve_region_names(record)
    cfg = DataGoCandidateConfig(
        endpoint_url=settings.data_go_candidate_endpoint_url,
        service_key=settings.data_go_kr_key,
        sg_id=election_id if election_id != "unknown" else settings.data_go_candidate_sg_id,
        sg_typecode=sg_typecode,
        sd_name=sd_name or settings.data_go_candidate_sd_name,
        sgg_name=sgg_name or settings.data_go_candidate_sgg_name,
        timeout_sec=settings.data_go_candidate_timeout_sec,
        max_retries=settings.data_go_candidate_max_retries,
        cache_ttl_sec=settings.data_go_candidate_cache_ttl_sec,
        requests_per_sec=settings.data_go_candidate_requests_per_sec,
        num_of_rows=settings.data_go_candidate_num_of_rows,
    )
    service = DataGoCandidateService(cfg)
    if not service.is_configured():
        return None
    return service


def _apply_candidate_verification(
    *,
    option_payload: dict[str, Any],
    record,
    candidate_name_set: set[str],
    candidate_party_map: dict[str, str | None],
    candidate_id_map: dict[str, str],
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> str | None:
    option_type = option_payload.get("option_type")
    if option_type not in {"candidate", "candidate_matchup"}:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 1.0
        option_payload["candidate_verify_matched_key"] = None
        return None

    option_name = str(option_payload.get("option_name") or "").strip()
    normalized_name = _normalize_candidate_token(option_name)
    party_name = candidate_party_map.get(normalized_name) or _normalize_party_name(option_payload.get("party_name"))
    matched_candidate_id = candidate_id_map.get(normalized_name)

    if _looks_like_noise_candidate(option_name):
        option_payload["candidate_verified"] = False
        option_payload["candidate_verify_source"] = "manual"
        option_payload["candidate_verify_confidence"] = 0.0
        option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
            source="noise",
            normalized_name=normalized_name,
            candidate_id=matched_candidate_id,
        )
        option_payload["needs_manual_review"] = True
        return "CANDIDATE_TOKEN_NOISE"

    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        service = _build_or_get_candidate_service(
            record=record,
            sg_typecode=sg_typecode,
            service_cache=service_cache,
        )
        if service is None:
            continue
        verified, confidence = service.verify_candidate(candidate_name=option_name, party_name=party_name)
        if verified:
            option_payload["candidate_verified"] = True
            option_payload["candidate_verify_source"] = "data_go"
            option_payload["candidate_verify_confidence"] = round(float(confidence), 3)
            option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
                source="data_go",
                normalized_name=normalized_name,
                candidate_id=matched_candidate_id,
            )
            return None

    if normalized_name in candidate_name_set:
        option_payload["candidate_verified"] = True
        option_payload["candidate_verify_source"] = "article_context"
        option_payload["candidate_verify_confidence"] = 0.68
        option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
            source="article_context",
            normalized_name=normalized_name,
            candidate_id=matched_candidate_id,
        )
        return None

    option_payload["candidate_verified"] = False
    option_payload["candidate_verify_source"] = "manual"
    option_payload["candidate_verify_confidence"] = 0.2
    option_payload["candidate_verify_matched_key"] = _candidate_verify_matched_key(
        source="manual",
        normalized_name=normalized_name,
        candidate_id=matched_candidate_id,
    )
    option_payload["needs_manual_review"] = True
    return "CANDIDATE_NOT_VERIFIED"


def _candidate_profile_field_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _candidate_profile_score(candidate_payload: dict[str, Any]) -> int:
    score = 0
    for field in CANDIDATE_PROFILE_FIELDS:
        if not _candidate_profile_field_missing(candidate_payload.get(field)):
            score += 1
    return score


def _normalize_candidate_profile_fields(candidate_payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate_payload)
    for field in CANDIDATE_PROFILE_FIELDS:
        normalized.setdefault(field, None)
    return normalized


def _build_or_get_candidate_service(
    *,
    record,
    sg_typecode: str,
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> DataGoCandidateService | None:
    sd_name, sgg_name = _resolve_region_names(record)
    cache_key = (
        _infer_election_id(record.observation.matchup_id),
        sd_name,
        sgg_name,
        sg_typecode,
    )
    if cache_key not in service_cache:
        service_cache[cache_key] = _build_candidate_service(record=record, sg_typecode=sg_typecode)
    return service_cache[cache_key]


def _enrich_candidate_profile(
    *,
    candidate_payload: dict[str, Any],
    record,
    service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None],
) -> tuple[dict[str, Any], str | None]:
    enriched = _normalize_candidate_profile_fields(candidate_payload)
    candidate_name = str(enriched.get("name_ko") or "").strip()
    if _looks_like_noise_candidate(candidate_name):
        return enriched, "CANDIDATE_PROFILE_NAME_INVALID"

    best = dict(enriched)
    best_score = _candidate_profile_score(best)
    for sg_typecode in _office_type_sg_types(record.observation.office_type):
        service = _build_or_get_candidate_service(
            record=record,
            sg_typecode=sg_typecode,
            service_cache=service_cache,
        )
        if service is None:
            continue
        candidate_try = _normalize_candidate_profile_fields(service.enrich_candidate(enriched))
        score = _candidate_profile_score(candidate_try)
        if score > best_score:
            best = candidate_try
            best_score = score

    required_missing = [
        field
        for field in CANDIDATE_PROFILE_REQUIRED_FOR_REVIEW
        if _candidate_profile_field_missing(best.get(field))
    ]
    if required_missing:
        return best, "CANDIDATE_PROFILE_INCOMPLETE:" + ",".join(required_missing)
    return best, None


def _normalize_option(option: PollOptionInput) -> tuple[dict, str | None]:
    payload = option.model_dump()
    scenario_key = payload.get("scenario_key")
    if isinstance(scenario_key, str):
        scenario_key = scenario_key.strip()
    payload["scenario_key"] = scenario_key or "default"

    candidate_id = payload.get("candidate_id")
    if isinstance(candidate_id, str):
        candidate_id = candidate_id.strip() or None
    payload["candidate_id"] = candidate_id

    party_name = payload.get("party_name")
    if isinstance(party_name, str):
        party_name = party_name.strip() or None
    payload["party_name"] = party_name

    scenario_title = payload.get("scenario_title")
    if isinstance(scenario_title, str):
        scenario_title = scenario_title.strip() or None
    payload["scenario_title"] = scenario_title

    candidate_verify_matched_key = payload.get("candidate_verify_matched_key")
    if isinstance(candidate_verify_matched_key, str):
        candidate_verify_matched_key = candidate_verify_matched_key.strip() or None
    payload["candidate_verify_matched_key"] = candidate_verify_matched_key

    party_inference_evidence = payload.get("party_inference_evidence")
    if isinstance(party_inference_evidence, (dict, list)):
        party_inference_evidence = json.dumps(
            party_inference_evidence,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    elif isinstance(party_inference_evidence, str):
        party_inference_evidence = party_inference_evidence.strip() or None
    else:
        party_inference_evidence = None
    payload["party_inference_evidence"] = party_inference_evidence

    normalized_option_type, classification_needs_review, classification_reason = normalize_option_type(
        payload.get("option_type"),
        payload.get("option_name"),
    )
    payload["option_type"] = normalized_option_type

    if payload["value_min"] is None and payload["value_max"] is None and payload["value_mid"] is None:
        normalized = normalize_percentage(payload.get("value_raw"))
        payload["value_min"] = normalized.value_min
        payload["value_max"] = normalized.value_max
        payload["value_mid"] = normalized.value_mid
        payload["is_missing"] = normalized.is_missing

    confidence = payload.get("party_inference_confidence")
    if payload.get("party_inferred") and confidence is not None:
        try:
            payload["needs_manual_review"] = float(confidence) < PARTY_INFERENCE_REVIEW_THRESHOLD
        except (TypeError, ValueError):
            payload["needs_manual_review"] = False
    else:
        payload["needs_manual_review"] = bool(payload.get("needs_manual_review", False))

    if classification_needs_review:
        payload["needs_manual_review"] = True
    return payload, classification_reason


def _scenario_name_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = SCENARIO_NAME_RE.search(text)
    return match.group(0) if match else text


def _scenario_value(option: dict[str, Any]) -> float:
    value_mid = option.get("value_mid")
    if value_mid is None:
        return float("-inf")
    try:
        return float(value_mid)
    except (TypeError, ValueError):
        return float("-inf")


def _extract_h2h_pairs(survey_name: str) -> list[tuple[str, float, str, float]]:
    pairs: list[tuple[str, float, str, float]] = []
    seen: set[tuple[str, float, str, float]] = set()
    for match in SCENARIO_H2H_PAIR_RE.finditer(survey_name):
        left_name = _scenario_name_token(match.group(1))
        right_name = _scenario_name_token(match.group(3))
        if not left_name or not right_name or left_name == right_name:
            continue
        try:
            left_value = float(match.group(2))
            right_value = float(match.group(4))
        except (TypeError, ValueError):
            continue
        key = (left_name, left_value, right_name, right_value)
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return pairs


def _extract_multi_anchor(survey_name: str) -> tuple[str, float] | None:
    match = SCENARIO_MULTI_SINGLE_RE.search(survey_name)
    if not match:
        return None
    name = _scenario_name_token(match.group(1))
    if not name:
        return None
    try:
        value = float(match.group(2))
    except (TypeError, ValueError):
        return None
    return name, value


def _extract_multi_candidates(survey_name: str) -> list[tuple[str, float]]:
    text = str(survey_name or "")
    if "다자대결" not in text:
        return []

    start = text.find("다자대결")
    segment = text[start:]
    # keep the parsing window short to avoid mixing unrelated survey snippets.
    for stop_token in (" 양자대결", " 가상대결", " 여론조사", "표본오차", "응답률"):
        stop_idx = segment.find(stop_token)
        if stop_idx > 0:
            segment = segment[:stop_idx]
            break

    seen_names: set[str] = set()
    rows: list[tuple[str, float]] = []
    for match in SCENARIO_MULTI_ITEM_RE.finditer(segment):
        name = _scenario_name_token(match.group(1))
        if not name or name in seen_names:
            continue
        try:
            value = float(match.group(2))
        except (TypeError, ValueError):
            continue
        seen_names.add(name)
        rows.append((name, value))
    return rows if len(rows) >= 3 else []


def _match_candidate_index(
    *,
    options: list[dict[str, Any]],
    candidate_indexes: list[int],
    names_by_index: dict[int, str],
    name: str,
    value: float,
    exclude: set[int],
) -> int | None:
    candidates = [i for i in candidate_indexes if i not in exclude and names_by_index.get(i) == name]
    if not candidates:
        return None
    exact = [i for i in candidates if abs(_scenario_value(options[i]) - value) <= 0.15]
    if not exact:
        return None
    exact.sort(key=lambda i: abs(_scenario_value(options[i]) - value))
    return exact[0]


def _clone_candidate_option(
    *,
    options: list[dict[str, Any]],
    candidate_indexes: list[int],
    names_by_index: dict[int, str],
    name: str,
    value: float,
) -> int | None:
    template_indexes = [i for i in candidate_indexes if names_by_index.get(i) == name]
    generic_template = False
    if not template_indexes:
        if not candidate_indexes:
            return None
        generic_template = True
        template_indexes = [candidate_indexes[0]]
    template_indexes.sort(key=lambda i: abs(_scenario_value(options[i]) - value))
    row = dict(options[template_indexes[0]])
    row["option_name"] = name
    row["value_mid"] = value
    row["value_raw"] = f"{value:.1f}%"
    if generic_template:
        row["candidate_id"] = None
        row["party_name"] = None
        row["party_inferred"] = False
        row["party_inference_source"] = None
        row["party_inference_confidence"] = None
        row["party_inference_evidence"] = None
        row["candidate_verified"] = False
        row["candidate_verify_source"] = "manual"
        row["candidate_verify_confidence"] = 0.0
        row["candidate_verify_matched_key"] = name
        row["needs_manual_review"] = True
    row["scenario_key"] = "default"
    row["scenario_type"] = None
    row["scenario_title"] = None
    options.append(row)
    return len(options) - 1


def _scenario_key_is_default(value: Any) -> bool:
    key = str(value or "").strip()
    return key in {"", "default"}


def _detect_scenario_parse_incomplete(
    *,
    survey_name: str | None,
    article_title: str | None,
    article_raw_text: str | None,
    options: list[dict[str, Any]],
) -> tuple[bool, int, list[str]]:
    text = " ".join(x for x in [survey_name, article_title, article_raw_text] if isinstance(x, str))
    if "다자대결" not in text:
        return False, 0, []
    candidate_names: set[str] = set()
    for row in options:
        if row.get("option_type") not in {"candidate", "candidate_matchup"}:
            continue
        name = _scenario_name_token(row.get("option_name"))
        if name:
            candidate_names.add(name)
    names = sorted(candidate_names)
    return len(names) < 3, len(names), names


def _has_explicit_candidate_scenarios(options: list[dict[str, Any]]) -> bool:
    for row in options:
        if row.get("option_type") != "candidate_matchup":
            continue
        if _scenario_key_is_default(row.get("scenario_key")):
            continue
        return True
    return False


def _backfill_multi_from_default_candidates(
    *,
    options: list[dict[str, Any]],
    default_rows: list[dict[str, Any]],
) -> bool:
    multi_key = ""
    multi_title = "다자대결"
    multi_names: set[str] = set()

    for row in options:
        if row.get("option_type") != "candidate_matchup":
            continue
        key = str(row.get("scenario_key") or "").strip()
        scenario_type = str(row.get("scenario_type") or "").strip()
        if scenario_type != "multi_candidate" and not key.startswith("multi-"):
            continue
        if not multi_key:
            multi_key = key
        title = str(row.get("scenario_title") or "").strip()
        if title:
            multi_title = title
        name = _scenario_name_token(row.get("option_name"))
        if name:
            multi_names.add(name)
            row["option_name"] = name
            row["scenario_type"] = "multi_candidate"
            row["scenario_title"] = multi_title

    if not multi_key:
        return False

    changed = False
    for default_row in default_rows:
        name = _scenario_name_token(default_row.get("option_name"))
        if not name or name in multi_names:
            continue
        options.append(
            {
                "option_type": "candidate_matchup",
                "option_name": name,
                "candidate_id": None,
                "party_name": None,
                "scenario_key": multi_key,
                "scenario_type": "multi_candidate",
                "scenario_title": multi_title,
                "value_raw": default_row.get("value_raw"),
                "value_min": default_row.get("value_min"),
                "value_max": default_row.get("value_max"),
                "value_mid": default_row.get("value_mid"),
                "is_missing": bool(default_row.get("is_missing", False)),
                "party_inferred": False,
                "party_inference_source": None,
                "party_inference_confidence": None,
                "party_inference_evidence": None,
                "candidate_verified": True,
                "candidate_verify_source": None,
                "candidate_verify_confidence": None,
                "needs_manual_review": False,
            }
        )
        multi_names.add(name)
        changed = True
    return changed


def _repair_candidate_matchup_scenarios(
    *,
    survey_name: str | None,
    options: list[dict[str, Any]],
) -> bool:
    text = str(survey_name or "")
    if "다자대결" not in text and "양자대결" not in text:
        return False

    candidate_indexes = [i for i, row in enumerate(options) if row.get("option_type") == "candidate_matchup"]
    if len(candidate_indexes) < 3:
        return False

    names_by_index = {i: _scenario_name_token(options[i].get("option_name")) for i in candidate_indexes}
    multi_candidates = _extract_multi_candidates(text)
    counts: dict[str, int] = {}
    for idx in candidate_indexes:
        name = names_by_index[idx]
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1

    default_candidate_indexes = [i for i in candidate_indexes if _scenario_key_is_default(options[i].get("scenario_key"))]
    explicit_candidate_indexes = [i for i in candidate_indexes if i not in default_candidate_indexes]

    # Respect explicit scenario annotations from extractor when they are complete.
    if explicit_candidate_indexes and not default_candidate_indexes:
        return False

    # Canonicalization for partially split payloads:
    # if explicit scenario rows exist together with default rows, move default rows into multi
    # and remove default candidate rows to avoid mixed/default leakage.
    if explicit_candidate_indexes and default_candidate_indexes:
        multi_key = ""
        multi_title = "다자대결"
        for idx in explicit_candidate_indexes:
            row = options[idx]
            key = str(row.get("scenario_key") or "").strip()
            scenario_type = str(row.get("scenario_type") or "").strip()
            if scenario_type == "multi_candidate" or key.startswith("multi-"):
                multi_key = key or multi_key
                title = str(row.get("scenario_title") or "").strip()
                if title:
                    multi_title = title
                break

        if not multi_key:
            anchor_name = ""
            for idx in explicit_candidate_indexes:
                key = str(options[idx].get("scenario_key") or "").strip()
                if key.startswith("h2h-"):
                    parts = [part for part in key.split("-")[1:] if part]
                    if parts:
                        anchor_name = parts[0]
                        break
            if not anchor_name:
                for idx in explicit_candidate_indexes:
                    if names_by_index.get(idx):
                        anchor_name = names_by_index[idx]
                        break
            if not anchor_name:
                for idx in default_candidate_indexes:
                    if names_by_index.get(idx):
                        anchor_name = names_by_index[idx]
                        break
            multi_key = f"multi-{anchor_name or '후보'}"

        default_name_to_row: dict[str, dict[str, Any]] = {}
        for idx in default_candidate_indexes:
            row = dict(options[idx])
            name = names_by_index.get(idx) or _scenario_name_token(row.get("option_name"))
            if not name:
                continue
            row["option_name"] = name
            existing = default_name_to_row.get(name)
            if existing is None or _scenario_value(row) > _scenario_value(existing):
                default_name_to_row[name] = row

        default_index_set = set(default_candidate_indexes)
        options[:] = [row for i, row in enumerate(options) if i not in default_index_set]

        existing_multi_names: set[str] = set()
        candidate_indexes_after_cleanup = [
            i for i, row in enumerate(options) if row.get("option_type") == "candidate_matchup"
        ]
        names_after_cleanup = {
            i: _scenario_name_token(options[i].get("option_name"))
            for i in candidate_indexes_after_cleanup
        }
        for row in options:
            if row.get("option_type") != "candidate_matchup":
                continue
            key = str(row.get("scenario_key") or "").strip()
            if key != multi_key:
                continue
            row["scenario_type"] = "multi_candidate"
            row["scenario_title"] = multi_title
            name = _scenario_name_token(row.get("option_name"))
            if not name:
                continue
            row["option_name"] = name
            existing_multi_names.add(name)

        if multi_candidates:
            changed = bool(default_index_set)
            selected_multi_rows: set[int] = set()
            for name, value in multi_candidates:
                matched_idx = _match_candidate_index(
                    options=options,
                    candidate_indexes=candidate_indexes_after_cleanup,
                    names_by_index=names_after_cleanup,
                    name=name,
                    value=value,
                    exclude=selected_multi_rows,
                )
                if matched_idx is None:
                    matched_idx = _clone_candidate_option(
                        options=options,
                        candidate_indexes=candidate_indexes_after_cleanup,
                        names_by_index=names_after_cleanup,
                        name=name,
                        value=value,
                    )
                    if matched_idx is not None:
                        candidate_indexes_after_cleanup.append(matched_idx)
                        names_after_cleanup[matched_idx] = name
                if matched_idx is None:
                    continue
                row = options[matched_idx]
                row["option_name"] = name
                row["value_mid"] = value
                row["value_raw"] = f"{value:.1f}%"
                row["scenario_key"] = multi_key
                row["scenario_type"] = "multi_candidate"
                row["scenario_title"] = multi_title
                selected_multi_rows.add(matched_idx)
                changed = True

            if selected_multi_rows:
                options[:] = [
                    row
                    for idx, row in enumerate(options)
                    if not (
                        row.get("option_type") == "candidate_matchup"
                        and str(row.get("scenario_key") or "").strip() == multi_key
                        and idx not in selected_multi_rows
                    )
                ]
                return changed

        changed = bool(default_index_set)
        for name, template_row in default_name_to_row.items():
            if name in existing_multi_names:
                continue
            new_row = dict(template_row)
            new_row["option_name"] = name
            new_row["scenario_key"] = multi_key
            new_row["scenario_type"] = "multi_candidate"
            new_row["scenario_title"] = multi_title
            options.append(new_row)
            existing_multi_names.add(name)
            changed = True

        return changed

    # Enhanced split: when survey text includes multiple explicit h2h pairs + multi,
    # materialize separate scenario groups (h2h/h2h/multi) even if source options are under default.
    h2h_pairs = _extract_h2h_pairs(text)
    if "다자대결" in text and len(h2h_pairs) >= 2:
        assigned = False
        used_indexes: set[int] = set()
        anchor_for_multi: str | None = None
        candidate_indexes_all = list(candidate_indexes)
        names_all = dict(names_by_index)

        for left_name, left_value, right_name, right_value in h2h_pairs:
            left_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=left_name,
                value=left_value,
                exclude=used_indexes,
            )
            if left_idx is None:
                left_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=left_name,
                    value=left_value,
                )
                if left_idx is not None:
                    candidate_indexes_all.append(left_idx)
                    names_all[left_idx] = left_name

            right_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=right_name,
                value=right_value,
                exclude=used_indexes,
            )
            if right_idx is None:
                right_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=right_name,
                    value=right_value,
                )
                if right_idx is not None:
                    candidate_indexes_all.append(right_idx)
                    names_all[right_idx] = right_name

            if left_idx is None or right_idx is None or left_idx == right_idx:
                continue

            scenario_key = f"h2h-{left_name}-{right_name}"
            scenario_title = f"{left_name} vs {right_name}"
            for idx, option_name, option_value in (
                (left_idx, left_name, left_value),
                (right_idx, right_name, right_value),
            ):
                row = options[idx]
                row["option_name"] = option_name
                row["value_mid"] = option_value
                row["value_raw"] = f"{option_value:.1f}%"
                row["scenario_key"] = scenario_key
                row["scenario_type"] = "head_to_head"
                row["scenario_title"] = scenario_title
                used_indexes.add(idx)
            if anchor_for_multi is None:
                anchor_for_multi = left_name
            assigned = True

        if assigned and multi_candidates:
            multi_key = f"multi-{anchor_for_multi or multi_candidates[0][0]}"
            multi_selected: set[int] = set()
            for name, value in multi_candidates:
                idx = _match_candidate_index(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=name,
                    value=value,
                    exclude=used_indexes | multi_selected,
                )
                if idx is None:
                    idx = _clone_candidate_option(
                        options=options,
                        candidate_indexes=candidate_indexes_all,
                        names_by_index=names_all,
                        name=name,
                        value=value,
                    )
                    if idx is not None:
                        candidate_indexes_all.append(idx)
                        names_all[idx] = name
                if idx is None:
                    continue
                row = options[idx]
                row["option_name"] = name
                row["value_mid"] = value
                row["value_raw"] = f"{value:.1f}%"
                row["scenario_key"] = multi_key
                row["scenario_type"] = "multi_candidate"
                row["scenario_title"] = "다자대결"
                multi_selected.add(idx)

            if multi_selected:
                selected_candidate_rows = used_indexes | multi_selected
                options[:] = [
                    row
                    for idx, row in enumerate(options)
                    if not (
                        row.get("option_type") == "candidate_matchup"
                        and idx not in selected_candidate_rows
                    )
                ]
                return True

        multi_indexes = [i for i in candidate_indexes_all if i not in used_indexes and names_all.get(i)]
        multi_anchor = _extract_multi_anchor(text)
        if multi_anchor is not None:
            multi_name, multi_value = multi_anchor
            multi_idx = _match_candidate_index(
                options=options,
                candidate_indexes=candidate_indexes_all,
                names_by_index=names_all,
                name=multi_name,
                value=multi_value,
                exclude=used_indexes,
            )
            if multi_idx is None:
                multi_idx = _clone_candidate_option(
                    options=options,
                    candidate_indexes=candidate_indexes_all,
                    names_by_index=names_all,
                    name=multi_name,
                    value=multi_value,
                )
                if multi_idx is not None:
                    candidate_indexes_all.append(multi_idx)
                    names_all[multi_idx] = multi_name
            if multi_idx is not None and multi_idx not in multi_indexes:
                multi_indexes.append(multi_idx)
                row = options[multi_idx]
                row["option_name"] = multi_name
                row["value_mid"] = multi_value
                row["value_raw"] = f"{multi_value:.1f}%"

        if assigned and multi_indexes:
            multi_key = f"multi-{anchor_for_multi or names_all.get(multi_indexes[0]) or '후보'}"
            for idx in multi_indexes:
                row = options[idx]
                row["scenario_key"] = multi_key
                row["scenario_type"] = "multi_candidate"
                row["scenario_title"] = "다자대결"
            return True

    duplicate_names = [name for name, cnt in counts.items() if cnt >= 2]
    if not duplicate_names:
        return False

    duplicate_names.sort(
        key=lambda name: max(_scenario_value(options[i]) for i in candidate_indexes if names_by_index[i] == name),
        reverse=True,
    )
    anchor_name = duplicate_names[0]
    anchor_indexes = [i for i in candidate_indexes if names_by_index[i] == anchor_name]
    anchor_indexes.sort(key=lambda i: _scenario_value(options[i]), reverse=True)
    anchor_h2h_idx = anchor_indexes[0]
    anchor_multi_idx = anchor_indexes[-1]

    partner_candidates = [i for i in candidate_indexes if names_by_index[i] != anchor_name]
    if not partner_candidates:
        return False
    partner_candidates.sort(key=lambda i: _scenario_value(options[i]), reverse=True)
    partner_h2h_idx = partner_candidates[0]
    partner_name = names_by_index[partner_h2h_idx] or "후보"

    h2h_key = f"h2h-{anchor_name}-{partner_name}"
    h2h_title = f"{anchor_name} vs {partner_name}"
    multi_key = f"multi-{anchor_name}"
    multi_title = "다자대결"

    for idx in (anchor_h2h_idx, partner_h2h_idx):
        row = options[idx]
        row["scenario_key"] = h2h_key
        row["scenario_type"] = "head_to_head"
        row["scenario_title"] = h2h_title

    for idx in candidate_indexes:
        if idx in {anchor_h2h_idx, partner_h2h_idx}:
            continue
        row = options[idx]
        row["scenario_key"] = multi_key
        row["scenario_type"] = "multi_candidate"
        row["scenario_title"] = multi_title

    if anchor_multi_idx not in {anchor_h2h_idx, partner_h2h_idx}:
        row = options[anchor_multi_idx]
        row["scenario_key"] = multi_key
        row["scenario_type"] = "multi_candidate"
        row["scenario_title"] = multi_title

    return True


def ingest_payload(payload: IngestPayload, repo) -> IngestResult:
    run_id = repo.create_ingestion_run(payload.run_type, payload.extractor_version, payload.llm_model)
    processed_count = 0
    error_count = 0
    date_inference_failed_count = 0
    date_inference_estimated_count = 0
    candidate_service_cache: dict[tuple[str, str | None, str | None, str], DataGoCandidateService | None] = {}
    candidate_profile_review_marked: set[str] = set()

    for record in payload.records:
        try:
            survey_end_cutoff_reason = survey_end_date_cutoff_reason(record.observation.survey_end_date)
            if survey_end_cutoff_reason != "PASS":
                error_count += 1
                try:
                    repo.insert_review_queue(
                        entity_type="ingest_record",
                        entity_id=record.observation.observation_key,
                        issue_type="ingestion_error",
                        review_note=(
                            "STALE_CYCLE_BLOCK "
                            f"reason={survey_end_cutoff_reason} "
                            f"survey_end_date={record.observation.survey_end_date} "
                            f"cutoff={SURVEY_END_DATE_CUTOFF.isoformat()}"
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass
                continue

            article_source = has_article_source(
                source_channel=record.observation.source_channel,
                source_channels=record.observation.source_channels,
            )
            if article_source:
                cutoff_reason = published_at_cutoff_reason(record.article.published_at)
                if cutoff_reason != "PASS":
                    error_count += 1
                    parsed_published_at = parse_datetime_like(record.article.published_at)
                    LOGGER.info(
                        "collector ingest excluded by article cutoff: reason=old_article_cutoff "
                        "observation_key=%s published_at=%s policy_reason=%s cutoff=%s",
                        record.observation.observation_key,
                        parsed_published_at.isoformat(timespec="seconds") if parsed_published_at else None,
                        cutoff_reason,
                        ARTICLE_PUBLISHED_AT_CUTOFF_ISO,
                    )
                    try:
                        repo.insert_review_queue(
                            entity_type="ingest_record",
                            entity_id=record.observation.observation_key,
                            issue_type="ingestion_error",
                            review_note=(
                                "ARTICLE_PUBLISHED_AT_CUTOFF_BLOCK "
                                "reason=old_article_cutoff "
                                f"policy_reason={cutoff_reason} "
                                f"published_at={parsed_published_at.isoformat(timespec='seconds') if parsed_published_at else None} "
                                f"cutoff={ARTICLE_PUBLISHED_AT_CUTOFF_ISO}"
                            ),
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    continue

            hardguard_applied, hardguard_keyword = _apply_scope_hardguard(record)
            if hardguard_applied:
                LOGGER.info(
                    "collector scope hardguard applied: observation_key=%s keyword=%s office_type=%s region_code=%s matchup_id=%s",
                    record.observation.observation_key,
                    hardguard_keyword,
                    record.observation.office_type,
                    record.observation.region_code,
                    record.observation.matchup_id,
                )

            if record.region:
                repo.upsert_region(record.region.model_dump())

            observation_payload = record.observation.model_dump()
            _apply_survey_name_matchup_correction(
                observation_payload=observation_payload,
                article_title=getattr(record.article, "title", None),
            )
            scope_resolution = _resolve_observation_scope(observation_payload)
            if scope_resolution.hard_fail_reason:
                error_count += 1
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=scope_resolution.hard_fail_reason,
                    )
                except Exception:  # noqa: BLE001
                    pass
                continue

            observation_payload["audience_scope"] = scope_resolution.scope
            observation_payload["audience_region_code"] = scope_resolution.audience_region_code
            repo.upsert_matchup(
                {
                    "matchup_id": observation_payload["matchup_id"],
                    "election_id": _infer_election_id(observation_payload["matchup_id"]),
                    "office_type": observation_payload["office_type"],
                    "region_code": observation_payload["region_code"],
                    "title": observation_payload["survey_name"],
                    "is_active": True,
                }
            )
            if scope_resolution.low_confidence_reason:
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=scope_resolution.low_confidence_reason,
                    )
                except Exception:  # noqa: BLE001
                    pass

            candidate_rows: list[dict[str, Any]] = []
            for candidate in record.candidates:
                candidate_payload = candidate.model_dump()
                enriched_candidate, profile_review_reason = _enrich_candidate_profile(
                    candidate_payload=candidate_payload,
                    record=record,
                    service_cache=candidate_service_cache,
                )
                repo.upsert_candidate(enriched_candidate)
                candidate_rows.append(enriched_candidate)
                candidate_id = str(enriched_candidate.get("candidate_id") or "").strip()
                if profile_review_reason and candidate_id and candidate_id not in candidate_profile_review_marked:
                    try:
                        repo.insert_review_queue(
                            entity_type="candidate",
                            entity_id=candidate_id,
                            issue_type="mapping_error",
                            review_note=f"candidate profile manual review required: {profile_review_reason}",
                        )
                        candidate_profile_review_marked.add(candidate_id)
                    except Exception:  # noqa: BLE001
                        pass

            article_id = repo.upsert_article(record.article.model_dump())
            observation_poll_block_id = str(
                observation_payload.get("poll_block_id")
                or observation_payload.get("observation_key")
                or ""
            ).strip()
            if observation_poll_block_id:
                observation_payload["poll_block_id"] = observation_poll_block_id
            if not observation_payload.get("poll_fingerprint"):
                observation_payload["poll_fingerprint"] = build_poll_fingerprint(observation_payload)

            inference_mode = observation_payload.get("date_inference_mode")
            inference_confidence = observation_payload.get("date_inference_confidence")
            inference_uncertain = False
            if inference_mode == "estimated_timestamp":
                date_inference_estimated_count += 1
                inference_uncertain = True
            if inference_mode in {"strict_fail_blocked", "failed"}:
                date_inference_failed_count += 1
                inference_uncertain = True
            if inference_confidence is not None and float(inference_confidence) < 0.8:
                inference_uncertain = True

            observation_id = repo.upsert_poll_observation(
                observation_payload,
                article_id=article_id,
                ingestion_run_id=run_id,
            )

            candidate_name_set = {
                _normalize_candidate_token(candidate.get("name_ko"))
                for candidate in candidate_rows
                if _normalize_candidate_token(candidate.get("name_ko"))
            }
            candidate_party_counter_map: dict[str, Counter[str]] = {}
            for candidate in candidate_rows:
                normalized_name = _normalize_candidate_token(candidate.get("name_ko"))
                party_name = _normalize_party_name(candidate.get("party_name"))
                if not normalized_name or not party_name:
                    continue
                candidate_party_counter_map.setdefault(normalized_name, Counter())[party_name] += 1
            candidate_party_map = {
                name: counter.most_common(1)[0][0]
                for name, counter in candidate_party_counter_map.items()
                if counter
            }
            candidate_id_map = {
                _normalize_candidate_token(candidate.get("name_ko")): str(candidate.get("candidate_id") or "").strip()
                for candidate in candidate_rows
                if _normalize_candidate_token(candidate.get("name_ko")) and str(candidate.get("candidate_id") or "").strip()
            }

            party_inference_low_confidence: list[tuple[str, float]] = []
            option_type_manual_review: list[tuple[str, str]] = []
            candidate_verify_manual_review: list[tuple[str, str]] = []
            normalized_options: list[dict[str, Any]] = []
            classification_reason_by_id: dict[int, str | None] = {}
            for option in record.options:
                normalized_option, classification_reason = _normalize_option(option)
                option_poll_block_id = str(normalized_option.get("poll_block_id") or "").strip()
                if not option_poll_block_id:
                    normalized_option["poll_block_id"] = observation_poll_block_id or None
                elif observation_poll_block_id and option_poll_block_id != observation_poll_block_id:
                    normalized_option["poll_block_id"] = observation_poll_block_id
                    try:
                        repo.insert_review_queue(
                            entity_type="poll_observation",
                            entity_id=record.observation.observation_key,
                            issue_type="metadata_cross_contamination",
                            review_note=(
                                "POLL_BLOCK_ID_MISMATCH_IN_OBSERVATION "
                                f"observation_poll_block_id={observation_poll_block_id} "
                                f"option_poll_block_id={option_poll_block_id}"
                            ),
                        )
                    except Exception:  # noqa: BLE001
                        pass
                normalized_options.append(normalized_option)
                classification_reason_by_id[id(normalized_option)] = classification_reason
            _repair_candidate_matchup_scenarios(
                survey_name=record.observation.survey_name,
                options=normalized_options,
            )
            if _has_explicit_candidate_scenarios(normalized_options):
                fetch_default = getattr(repo, "fetch_candidate_default_poll_options", None)
                if callable(fetch_default):
                    prior_defaults = fetch_default(observation_id) or []
                    if prior_defaults:
                        _backfill_multi_from_default_candidates(
                            options=normalized_options,
                            default_rows=prior_defaults,
                        )
                cleanup_default = getattr(repo, "delete_candidate_default_poll_options", None)
                if callable(cleanup_default):
                    cleanup_default(observation_id)

            scenario_incomplete, scenario_candidate_count, scenario_candidate_names = _detect_scenario_parse_incomplete(
                survey_name=record.observation.survey_name,
                article_title=record.article.title,
                article_raw_text=record.article.raw_text,
                options=normalized_options,
            )
            if scenario_incomplete:
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="scenario_parse_incomplete",
                        review_note=(
                            "SCENARIO_PARSE_INCOMPLETE "
                            f"candidate_count={scenario_candidate_count} "
                            f"candidates={','.join(scenario_candidate_names) if scenario_candidate_names else '-'} "
                            f"matchup_id={record.observation.matchup_id}"
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass

            for normalized_option in normalized_options:
                classification_reason = classification_reason_by_id.get(id(normalized_option))
                _apply_party_inference_v3(
                    option_payload=normalized_option,
                    record=record,
                    candidate_party_counter_map=candidate_party_counter_map,
                    service_cache=candidate_service_cache,
                )
                candidate_verify_reason = _apply_candidate_verification(
                    option_payload=normalized_option,
                    record=record,
                    candidate_name_set=candidate_name_set,
                    candidate_party_map=candidate_party_map,
                    candidate_id_map=candidate_id_map,
                    service_cache=candidate_service_cache,
                )
                repo.upsert_poll_option(observation_id, normalized_option)
                if classification_reason:
                    option_type_manual_review.append(
                        (normalized_option.get("option_name", "unknown"), classification_reason)
                    )
                if candidate_verify_reason:
                    candidate_verify_manual_review.append(
                        (normalized_option.get("option_name", "unknown"), candidate_verify_reason)
                    )

                confidence = normalized_option.get("party_inference_confidence")
                if not normalized_option.get("party_inferred") or confidence is None:
                    continue
                try:
                    confidence_value = float(confidence)
                except (TypeError, ValueError):
                    continue
                if confidence_value < PARTY_INFERENCE_REVIEW_THRESHOLD:
                    party_inference_low_confidence.append(
                        (normalized_option.get("option_name", "unknown"), confidence_value)
                    )

            if inference_uncertain:
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="extract_error",
                        review_note=(
                            "date inference uncertainty: "
                            f"mode={inference_mode}, confidence={inference_confidence}"
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass
            if party_inference_low_confidence:
                detail = ", ".join(f"{name}:{confidence:.2f}" for name, confidence in party_inference_low_confidence)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="party_inference_low_confidence",
                        review_note=f"party inference confidence below {PARTY_INFERENCE_REVIEW_THRESHOLD}: {detail}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            if option_type_manual_review:
                detail = ", ".join(f"{name}:{reason}" for name, reason in option_type_manual_review)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=f"option_type manual review required: {detail}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            if candidate_verify_manual_review:
                detail = ", ".join(f"{name}:{reason}" for name, reason in candidate_verify_manual_review)
                try:
                    repo.insert_review_queue(
                        entity_type="poll_observation",
                        entity_id=record.observation.observation_key,
                        issue_type="mapping_error",
                        review_note=f"candidate verification manual review required: {detail}",
                    )
                except Exception:  # noqa: BLE001
                    pass

            processed_count += 1
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            rollback = getattr(repo, "rollback", None)
            if callable(rollback):
                rollback()
            issue_type = "ingestion_error"
            if isinstance(exc, DuplicateConflictError):
                issue_type = "DUPLICATE_CONFLICT"
            try:
                repo.insert_review_queue(
                    entity_type="ingest_record",
                    entity_id=record.observation.observation_key,
                    issue_type=issue_type,
                    review_note=str(exc),
                )
            except Exception:  # noqa: BLE001
                # Keep batch loop alive even when review_queue insert fails.
                pass

    status = "success" if error_count == 0 else "partial_success"
    repo.finish_ingestion_run(run_id, status, processed_count, error_count)
    update_counters = getattr(repo, "update_ingestion_policy_counters", None)
    if callable(update_counters):
        update_counters(
            run_id,
            date_inference_failed_count=date_inference_failed_count,
            date_inference_estimated_count=date_inference_estimated_count,
        )
    return IngestResult(run_id=run_id, processed_count=processed_count, error_count=error_count, status=status)
