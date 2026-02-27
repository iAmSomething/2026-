import re
import unicodedata
from datetime import date, datetime, timezone
import logging
from typing import Literal
from urllib.parse import unquote_plus

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError

from app.api.dependencies import get_candidate_data_go_service, get_repository, require_internal_job_token
from app.models.schemas import (
    BigMatchPoint,
    CandidateOut,
    DashboardBigMatchesOut,
    DashboardFilterStatsOut,
    DashboardQualityFreshnessOut,
    DashboardQualityOfficialOut,
    DashboardQualityOut,
    DashboardQualityReviewOut,
    DashboardMapLatestOut,
    DashboardSummaryOut,
    IngestPayload,
    JobRunOut,
    MapLatestPoint,
    MatchupOut,
    OpsFailureDistributionOut,
    OpsCoverageSummaryOut,
    OpsIngestionMetricsOut,
    OpsMetricsSummaryOut,
    OpsReviewMetricsOut,
    ScopeBreakdownOut,
    SourceChannelMixOut,
    OpsWarningRuleOut,
    ReviewQueueDecisionIn,
    ReviewQueueItemOut,
    ReviewQueueStatsOut,
    ReviewQueueTrendsOut,
    ReviewQueueTrendPointOut,
    ReviewQueueIssueCountOut,
    ReviewQueueErrorCountOut,
    RegionElectionOut,
    RegionOut,
    SourceTraceOut,
    SummaryPoint,
    TrendPoint,
    TrendsOut,
)
from app.services.cutoff_policy import (
    SURVEY_END_DATE_CUTOFF,
    has_article_source,
    is_article_published_at_allowed,
    is_survey_end_date_allowed,
)
from app.services.candidate_token_policy import is_noise_candidate_token
from app.services.ingest_service import ingest_payload
from app.services.ingest_input_normalization import normalize_ingest_payload
from app.services.region_code_normalizer import normalize_region_code_input

router = APIRouter(prefix="/api/v1", tags=["v1"])
logger = logging.getLogger(__name__)

MATCHUP_ID_ALIASES = {
    "m_2026_seoul_mayor": "20260603|광역자치단체장|11-000",
}

PRESIDENT_JOB_APPROVAL_KEYWORDS = (
    "긍정",
    "부정",
    "직무",
    "국정수행",
    "잘한다",
    "잘못",
    "못한다",
)
ELECTION_FRAME_KEYWORDS = (
    "국정안정",
    "국정견제",
    "안정론",
    "견제론",
    "정권교체",
    "정권재창출",
    "정권심판",
    "정권지원",
    "선거성격",
    "프레임",
)
MAP_LATEST_NOISE_TOKENS = {
    "양자대결",
    "오차는",
    "오차범위",
    "표본오차",
    "응답률",
    "조사기관",
    "여론조사",
    "지지율",
    "가상대결",
}
MAP_LATEST_CANDIDATE_RE = re.compile(r"^[가-힣]{2,4}$")
MAP_LATEST_LEGACY_TITLE_RE = re.compile(r"\[(?:19|20)\d{2}[^]]*선거[^]]*\]")
ARTICLE_AGGREGATE_HINTS = ("집계", "aggregate", "평균", "메타", "종합")
SOURCE_GRADE_SCORE = {
    "S": 5,
    "A": 4,
    "B": 3,
    "C": 2,
    "D": 1,
}
SUMMARY_SELECTION_POLICY_VERSION = "summary_single_set_v1"
MAP_LATEST_CANDIDATE_NAME_RE = re.compile(r"^[가-힣]{2,8}$")
MAP_LATEST_GENERIC_OPTION_EXACT_TOKENS = {
    "양자대결",
    "다자대결",
    "가상대결",
    "오차",
    "오차는",
    "응답률",
    "응답률은",
    "지지율",
    "지지율은",
    "표본오차",
    "오차범위",
    "여론조사",
    "민주",
    "민주당",
    "국힘",
    "국민의힘",
    "같은",
    "차이",
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
}
MAP_LATEST_GENERIC_OPTION_SUBSTRINGS = {
    "오차",
    "응답률",
    "지지율",
    "지지도",
    "지지",
    "표본오차",
    "오차범위",
    "여론조사",
    "재정자립",
    "적합도",
    "선호도",
    "안정론",
    "견제론",
    "정권",
    "긍정평가",
    "부정평가",
}
MAP_LATEST_LEGACY_TITLE_KEYWORDS = {
    "대통령선거",
    "대통령 선거",
    "총선",
    "국회의원",
    "국회의원선거",
}
MAP_LATEST_TARGET_YEAR = "2026"
CANDIDATE_PROFILE_TRACKED_FIELDS = (
    "party_name",
    "gender",
    "birth_date",
    "job",
    "career_summary",
    "election_history",
)
CANDIDATE_PROFILE_REQUIRED_FIELDS = (
    "party_name",
    "career_summary",
    "election_history",
)


def _build_scope_breakdown(rows: list[dict]) -> dict[str, int]:
    counts = {"national": 0, "regional": 0, "local": 0, "unknown": 0}
    for row in rows:
        scope = row.get("audience_scope")
        if scope in {"national", "regional", "local"}:
            counts[scope] += 1
        else:
            counts["unknown"] += 1
    return counts


def _to_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _decode_query_text(value: str) -> str:
    if "%" not in value and "+" not in value:
        return value
    try:
        return unquote_plus(value)
    except Exception:
        return value


def _normalize_region_query(raw_query: str) -> str:
    text = raw_query.replace("\u3000", " ").strip()
    if not text:
        return ""

    # Some clients send double-encoded non-ASCII query strings.
    for _ in range(2):
        decoded = _decode_query_text(text)
        if decoded == text:
            break
        text = decoded

    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_candidate_profile_field_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        return text or None
    text = str(value).strip()
    return text or None


def _normalize_candidate_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_candidate_profile_provenance(*, base_row: dict, final_row: dict) -> dict[str, str]:
    provenance: dict[str, str] = {}
    for field in CANDIDATE_PROFILE_TRACKED_FIELDS:
        base_value = _normalize_candidate_profile_field_value(base_row.get(field))
        final_value = _normalize_candidate_profile_field_value(final_row.get(field))
        if final_value is None:
            provenance[field] = "missing"
        elif base_value is None:
            provenance[field] = "data_go"
        elif base_value == final_value:
            provenance[field] = "ingest"
        else:
            provenance[field] = "data_go"
    return provenance


def _derive_candidate_profile_source(provenance: dict[str, str]) -> Literal["data_go", "ingest", "mixed", "none"]:
    values = {value for value in provenance.values() if value in {"data_go", "ingest"}}
    if values == {"data_go"}:
        return "data_go"
    if values == {"ingest"}:
        return "ingest"
    if values == {"data_go", "ingest"}:
        return "mixed"
    return "none"


def _derive_candidate_profile_completeness(row: dict) -> Literal["complete", "partial", "empty"]:
    required_presence = [
        _normalize_candidate_profile_field_value(row.get(field)) is not None for field in CANDIDATE_PROFILE_REQUIRED_FIELDS
    ]
    if all(required_presence):
        return "complete"
    if any(required_presence):
        return "partial"
    return "empty"


def _derive_source_meta(row: dict) -> dict:
    raw_channels = row.get("source_channels") or []
    channels = {str(ch).strip().lower() for ch in raw_channels if ch is not None}
    source_channel = str(row.get("source_channel") or "").strip().lower()
    if source_channel:
        channels.add(source_channel)

    has_article = "article" in channels or source_channel == "article"
    has_nesdc = "nesdc" in channels or source_channel == "nesdc"

    if has_article and has_nesdc:
        source_priority = "mixed"
    elif has_nesdc:
        source_priority = "official"
    else:
        source_priority = "article"

    observation_updated_at = _to_datetime(row.get("observation_updated_at"))
    article_published_at = _to_datetime(row.get("article_published_at"))
    official_release_at = _to_datetime(row.get("official_release_at"))
    if official_release_at is None and has_nesdc:
        official_release_at = observation_updated_at

    freshness_anchor = official_release_at or article_published_at or observation_updated_at
    freshness_hours = None
    if freshness_anchor is not None:
        delta_seconds = (datetime.now(timezone.utc) - freshness_anchor).total_seconds()
        freshness_hours = round(max(delta_seconds, 0.0) / 3600.0, 2)

    return {
        "source_priority": source_priority,
        "official_release_at": official_release_at,
        "article_published_at": article_published_at,
        "freshness_hours": freshness_hours,
        "is_official_confirmed": has_nesdc,
    }

def _build_source_trace(
    *,
    row: dict,
    source_meta: dict,
    selected_source_tier: Literal["official", "nesdc", "article_aggregate", "article"] | None = None,
    selected_source_channel: str | None = None,
) -> SourceTraceOut:
    return SourceTraceOut(
        source_priority=source_meta["source_priority"],
        source_channel=row.get("source_channel"),
        source_channels=row.get("source_channels") or [],
        selected_source_tier=selected_source_tier,
        selected_source_channel=selected_source_channel,
        official_release_at=source_meta["official_release_at"],
        article_published_at=source_meta["article_published_at"],
        freshness_hours=source_meta["freshness_hours"],
        is_official_confirmed=source_meta["is_official_confirmed"],
    )


def _normalize_title_fields(
    canonical_title: str | None,
    article_title: str | None,
    fallback_title: str,
) -> tuple[str, str | None, str | None]:
    normalized_canonical = str(canonical_title or "").strip() or str(fallback_title or "").strip() or None
    normalized_article = str(article_title or "").strip() or None
    if normalized_article and normalized_article == normalized_canonical:
        normalized_article = None
    return normalized_canonical or fallback_title, normalized_canonical, normalized_article


def _selection_freshness_anchor(row: dict) -> tuple[str, datetime | None]:
    official_release_at = _to_datetime(row.get("official_release_at"))
    article_published_at = _to_datetime(row.get("article_published_at"))
    observation_updated_at = _to_datetime(row.get("observation_updated_at"))
    if official_release_at is not None:
        return "official_release_at", official_release_at
    if article_published_at is not None:
        return "article_published_at", article_published_at
    if observation_updated_at is not None:
        return "observation_updated_at", observation_updated_at
    return "none", None


def _build_selection_trace(row: dict, *, selected_tier: str, source_meta: dict) -> dict:
    anchor_field, anchor_at = _selection_freshness_anchor(row)
    return {
        "algorithm_version": "representative_v2",
        "selection_policy_version": SUMMARY_SELECTION_POLICY_VERSION,
        "selected_source_tier": selected_tier,
        "selected_source_channel": row.get("source_channel"),
        "source_priority": source_meta.get("source_priority"),
        "freshness_anchor_field": anchor_field,
        "freshness_anchor_at": anchor_at,
        "legal_completeness_score": row.get("legal_completeness_score"),
        "legal_filled_count": row.get("legal_filled_count"),
        "legal_required_count": row.get("legal_required_count"),
        "source_grade": row.get("source_grade"),
        "audience_scope": row.get("audience_scope"),
    }


def _is_cutoff_eligible_row(row: dict) -> bool:
    if not is_survey_end_date_allowed(row.get("survey_end_date")):
        return False
    if not has_article_source(
        source_channel=row.get("source_channel"),
        source_channels=row.get("source_channels"),
    ):
        return True
    return is_article_published_at_allowed(row.get("article_published_at"))


def _normalize_candidate_token(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _is_map_latest_noise_option_name(option_name: str | None) -> bool:
    return is_noise_candidate_token(
        option_name,
        name_pattern=MAP_LATEST_CANDIDATE_RE,
        extra_exact_tokens=MAP_LATEST_NOISE_TOKENS,
        extra_substring_tokens=MAP_LATEST_GENERIC_OPTION_SUBSTRINGS,
    )


def _is_legacy_matchup_title(title: str | None) -> bool:
    text = str(title or "").strip()
    if not text:
        return False
    if MAP_LATEST_LEGACY_TITLE_RE.search(text):
        return True
    if "[2022" in text:
        return True
    return False


def _survey_end_before_cutoff(survey_end_date: date | str | None) -> bool:
    if survey_end_date is None:
        return False
    if isinstance(survey_end_date, date):
        survey_end = survey_end_date
    else:
        text = str(survey_end_date).strip()
        if not text:
            return False
        if "T" in text:
            text = text.split("T", 1)[0]
        try:
            survey_end = date.fromisoformat(text)
        except ValueError:
            return False
    return survey_end < SURVEY_END_DATE_CUTOFF


def _map_latest_exclusion_reason(row: dict) -> str | None:
    if _survey_end_before_cutoff(row.get("survey_end_date")):
        return "survey_end_date_before_cutoff"
    drop_reason = _map_latest_drop_reason(row)
    if drop_reason == "cutoff_blocked":
        return "article_published_at_before_cutoff"
    if drop_reason in {"generic_option_token", "invalid_candidate_name"}:
        return "invalid_candidate_option_name"
    if drop_reason == "legacy_title":
        return "legacy_matchup_title"
    if _is_legacy_matchup_title(row.get("title")):
        return "legacy_matchup_title"
    if _is_map_latest_noise_option_name(row.get("option_name")):
        return "invalid_candidate_option_name"
    return None


def _derive_dashboard_data_source(rows: list[dict]) -> str:
    channels: set[str] = set()
    for row in rows:
        if row.get("audience_scope") != "national":
            continue
        source_channel = str(row.get("source_channel") or "").strip().lower()
        if source_channel:
            channels.add(source_channel)
        for ch in row.get("source_channels") or []:
            normalized = str(ch).strip().lower()
            if normalized:
                channels.add(normalized)

    has_article = "article" in channels
    has_nesdc = "nesdc" in channels
    if has_article and has_nesdc:
        return "mixed"
    if has_nesdc:
        return "official"
    return "article"


def _normalize_matchup_id(raw_matchup_id: str) -> str:
    text = unquote_plus(raw_matchup_id).strip()
    if text in MATCHUP_ID_ALIASES:
        return MATCHUP_ID_ALIASES[text]
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3:
        return text
    election_id, office_type, region_code = parts
    region_normalized = normalize_region_code_input(region_code)
    compact_region = region_code.replace("_", "-")
    if region_normalized.canonical:
        compact_region = region_normalized.canonical
        if region_normalized.was_aliased:
            logger.info(
                "region_code_alias_normalized endpoint=matchups.get raw=%s canonical=%s",
                region_code,
                compact_region,
            )
    elif compact_region.isdigit() and len(compact_region) == 5:
        compact_region = f"{compact_region[:2]}-{compact_region[2:]}"
    return f"{election_id}|{office_type}|{compact_region}"


def _classify_presidential_option(option_name: str) -> str:
    normalized = re.sub(r"\s+", "", option_name or "")
    if any(keyword in normalized for keyword in ELECTION_FRAME_KEYWORDS):
        return "election_frame"
    if any(keyword in normalized for keyword in PRESIDENT_JOB_APPROVAL_KEYWORDS):
        return "president_job_approval"
    return "election_frame"


def _summary_source_tier(row: dict) -> Literal["official", "nesdc", "article_aggregate", "article"]:
    source_channel = str(row.get("source_channel") or "").strip().lower()
    source_channels = {str(ch).strip().lower() for ch in (row.get("source_channels") or []) if ch is not None}

    if source_channel == "official" or "official" in source_channels:
        return "official"
    if source_channel == "nesdc" or "nesdc" in source_channels:
        return "nesdc"

    pollster = str(row.get("pollster") or "").strip().lower()
    if any(hint in pollster for hint in ARTICLE_AGGREGATE_HINTS):
        return "article_aggregate"
    return "article"


def _summary_source_tier_score(tier: Literal["official", "nesdc", "article_aggregate", "article"]) -> int:
    return {
        "official": 4,
        "nesdc": 3,
        "article_aggregate": 2,
        "article": 1,
    }[tier]


def _summary_reliability_score(row: dict) -> int:
    source_grade = str(row.get("source_grade") or "").strip().upper()
    if source_grade in SOURCE_GRADE_SCORE:
        return SOURCE_GRADE_SCORE[source_grade]
    return 0


def _summary_row_sort_key(row: dict) -> tuple[int, float, int]:
    tier = _summary_source_tier(row)
    date_value = row.get("survey_end_date")
    date_score = 0.0
    if isinstance(date_value, date):
        date_score = float(date_value.toordinal())
    return (
        _summary_source_tier_score(tier),
        date_score,
        _summary_reliability_score(row),
    )


def _select_summary_representative(rows: list[dict]) -> tuple[dict, str]:
    selected = max(rows, key=_summary_row_sort_key)
    return selected, _summary_source_tier(selected)


def _summary_published_or_official_at(row: dict) -> datetime | None:
    return _to_datetime(row.get("official_release_at")) or _to_datetime(row.get("article_published_at"))


def _summary_updated_at(row: dict) -> datetime | None:
    return _to_datetime(row.get("observation_updated_at"))


def _summary_single_set_sort_key(row: dict) -> tuple[int, int, float, float]:
    tier = _summary_source_tier(row)
    source_grade_score = _summary_reliability_score(row)
    published_at = _summary_published_or_official_at(row)
    updated_at = _summary_updated_at(row)
    published_score = published_at.timestamp() if published_at is not None else 0.0
    updated_score = updated_at.timestamp() if updated_at is not None else 0.0
    # Policy: official_confirmed desc -> source_grade -> published_at desc -> updated_at desc
    return (
        1 if tier in {"official", "nesdc"} else 0,
        source_grade_score,
        published_score,
        updated_score,
    )


def _select_summary_single_set_representative(rows: list[dict]) -> tuple[dict, str]:
    selected = max(rows, key=_summary_single_set_sort_key)
    return selected, _summary_source_tier(selected)


def _summary_selected_reason(source_meta: dict) -> Literal["official_preferred", "latest_fallback"]:
    if bool(source_meta.get("is_official_confirmed")):
        return "official_preferred"
    return "latest_fallback"


def _normalize_map_candidate_token(option_name: str | None) -> str:
    token = re.sub(r"\s+", "", str(option_name or "").strip().lower())
    return re.sub(r"[^0-9a-z가-힣]", "", token)


def _is_generic_map_option_name(option_name: str | None) -> bool:
    token = _normalize_map_candidate_token(option_name)
    if not token:
        return True
    if token in MAP_LATEST_GENERIC_OPTION_EXACT_TOKENS:
        return True
    return any(part in token for part in MAP_LATEST_GENERIC_OPTION_SUBSTRINGS)


def _is_legacy_map_title(title: str | None) -> bool:
    text = str(title or "").strip()
    if not text:
        return True

    for year in re.findall(r"(?:19|20)\d{2}", text):
        if year != MAP_LATEST_TARGET_YEAR:
            return True

    return any(keyword in text for keyword in MAP_LATEST_LEGACY_TITLE_KEYWORDS)


def _map_latest_drop_reason(row: dict) -> str | None:
    if not _is_cutoff_eligible_row(row):
        return "cutoff_blocked"

    option_name = str(row.get("option_name") or "").strip()
    if _is_generic_map_option_name(option_name):
        return "generic_option_token"

    normalized_name = re.sub(r"\s+", "", option_name)
    if MAP_LATEST_CANDIDATE_NAME_RE.fullmatch(normalized_name) is None:
        return "invalid_candidate_name"

    if _is_legacy_map_title(row.get("title")):
        return "legacy_title"

    return None


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    as_of: date | None = Query(default=None),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_summary(as_of=as_of)
    party_support: list[SummaryPoint] = []
    president_job_approval: list[SummaryPoint] = []
    election_frame: list[SummaryPoint] = []
    eligible_rows = [row for row in rows if _is_cutoff_eligible_row(row)]
    national_rows = [row for row in eligible_rows if row.get("audience_scope") == "national"]
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in national_rows:
        option_name = str(row.get("option_name") or "").strip()
        if not option_name:
            continue
        if row["option_type"] == "party_support":
            bucket = "party_support"
        elif row["option_type"] == "president_job_approval":
            bucket = "president_job_approval"
        elif row["option_type"] == "election_frame":
            bucket = "election_frame"
        elif row["option_type"] == "presidential_approval":
            bucket = _classify_presidential_option(option_name)
        else:
            continue
        grouped.setdefault((bucket, option_name), []).append(row)

    for (bucket, _option_name), candidates in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        selected_row, selected_tier = _select_summary_single_set_representative(candidates)
        source_meta = _derive_source_meta(selected_row)
        selection_trace = _build_selection_trace(selected_row, selected_tier=selected_tier, source_meta=source_meta)
        point = SummaryPoint(
            option_name=selected_row["option_name"],
            value_mid=selected_row["value_mid"],
            pollster=selected_row["pollster"],
            survey_end_date=selected_row["survey_end_date"],
            audience_scope=selected_row.get("audience_scope"),
            audience_region_code=selected_row.get("audience_region_code"),
            source_priority=source_meta["source_priority"],
            selected_source_tier=selected_tier,
            selected_source_channel=selected_row.get("source_channel"),
            official_release_at=source_meta["official_release_at"],
            article_published_at=source_meta["article_published_at"],
            freshness_hours=source_meta["freshness_hours"],
            is_official_confirmed=source_meta["is_official_confirmed"],
            source_channel=selected_row.get("source_channel"),
            source_channels=selected_row.get("source_channels") or [],
            source_trace=_build_source_trace(
                row=selected_row,
                source_meta=source_meta,
                selected_source_tier=selected_tier,
                selected_source_channel=selected_row.get("source_channel"),
            ),
            selection_trace=selection_trace,
            selected_reason=_summary_selected_reason(source_meta),
            verified=selected_row["verified"],
        )
        if bucket == "party_support":
            party_support.append(point)
        elif bucket == "president_job_approval":
            president_job_approval.append(point)
        elif bucket == "election_frame":
            election_frame.append(point)

    deprecated_presidential_approval = list(president_job_approval)

    return DashboardSummaryOut(
        as_of=as_of,
        selection_policy_version=SUMMARY_SELECTION_POLICY_VERSION,
        data_source=_derive_dashboard_data_source(eligible_rows),
        party_support=party_support,
        president_job_approval=president_job_approval,
        election_frame=election_frame,
        presidential_approval=deprecated_presidential_approval,
        presidential_approval_deprecated=True,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(eligible_rows)),
    )


@router.get("/trends/{metric}", response_model=TrendsOut)
def get_trends(
    metric: Literal["party_support", "president_job_approval", "election_frame"],
    scope: Literal["national", "regional", "local"] = Query(default="national"),
    region_code: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    repo=Depends(get_repository),
):
    resolved_region_code = None
    if scope != "national":
        if not region_code:
            raise HTTPException(status_code=422, detail="region_code is required for regional/local scope")
        region_normalized = normalize_region_code_input(region_code)
        resolved_region_code = region_normalized.canonical or region_code
    elif region_code:
        region_normalized = normalize_region_code_input(region_code)
        resolved_region_code = region_normalized.canonical or region_code

    rows = repo.fetch_trends(
        metric=metric,
        scope=scope,
        region_code=resolved_region_code,
        days=days,
    )
    eligible_rows = [row for row in rows if _is_cutoff_eligible_row(row)]

    grouped: dict[tuple[date, str], list[dict]] = {}
    for row in eligible_rows:
        survey_end_date = row.get("survey_end_date")
        option_name = str(row.get("option_name") or "").strip()
        if not isinstance(survey_end_date, date) or not option_name:
            continue
        grouped.setdefault((survey_end_date, option_name), []).append(row)

    points: list[TrendPoint] = []
    for (survey_end_date, option_name), candidates in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        selected_row, selected_tier = _select_summary_representative(candidates)
        source_meta = _derive_source_meta(selected_row)
        points.append(
            TrendPoint(
                survey_end_date=survey_end_date,
                option_name=option_name,
                value_mid=selected_row.get("value_mid"),
                pollster=selected_row.get("pollster"),
                audience_scope=selected_row.get("audience_scope"),
                audience_region_code=selected_row.get("audience_region_code"),
                source_trace=_build_source_trace(
                    row=selected_row,
                    source_meta=source_meta,
                    selected_source_tier=selected_tier,
                    selected_source_channel=selected_row.get("source_channel"),
                ),
            )
        )

    return TrendsOut(
        metric=metric,
        scope=scope,
        region_code=resolved_region_code,
        days=days,
        points=points,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/dashboard/map-latest", response_model=DashboardMapLatestOut)
def get_dashboard_map_latest(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_map_latest(as_of=as_of, limit=limit)
    items = []
    kept_rows = []
    reason_counts: dict[str, int] = {}
    for row in rows:
        exclusion_reason = _map_latest_exclusion_reason(row)
        if exclusion_reason is not None:
            drop_reason = _map_latest_drop_reason(row)
            if exclusion_reason in {"survey_end_date_before_cutoff", "article_published_at_before_cutoff"}:
                reason_key = "stale_cycle"
            elif drop_reason == "cutoff_blocked":
                reason_key = "stale_cycle"
            else:
                reason_key = drop_reason or exclusion_reason
            reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
            continue
        kept_rows.append(row)

    logger.info(
        "dashboard_map_latest_sanity total=%d kept=%d excluded=%d reason_counts=%s",
        len(rows),
        len(kept_rows),
        len(rows) - len(kept_rows),
        reason_counts,
    )

    for row in kept_rows:
        selected_tier = _summary_source_tier(row)
        source_meta = _derive_source_meta(row)
        title, canonical_title, article_title = _normalize_title_fields(
            canonical_title=row.get("canonical_title"),
            article_title=row.get("article_title"),
            fallback_title=row["title"],
        )
        selection_trace = _build_selection_trace(row, selected_tier=selected_tier, source_meta=source_meta)
        items.append(
            MapLatestPoint(
                region_code=row["region_code"],
                office_type=row["office_type"],
                title=title,
                canonical_title=canonical_title,
                article_title=article_title,
                value_mid=row.get("value_mid"),
                survey_end_date=row.get("survey_end_date"),
                option_name=row.get("option_name"),
                audience_scope=row.get("audience_scope"),
                audience_region_code=row.get("audience_region_code"),
                source_priority=source_meta["source_priority"],
                selected_source_tier=selected_tier,
                selected_source_channel=row.get("source_channel"),
                official_release_at=source_meta["official_release_at"],
                article_published_at=source_meta["article_published_at"],
                freshness_hours=source_meta["freshness_hours"],
                is_official_confirmed=source_meta["is_official_confirmed"],
                source_channel=row.get("source_channel"),
                source_channels=row.get("source_channels") or [],
                source_trace=_build_source_trace(row=row, source_meta=source_meta),
                selection_trace=selection_trace,
            )
        )
    return DashboardMapLatestOut(
        as_of=as_of,
        items=items,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(kept_rows)),
        filter_stats=DashboardFilterStatsOut(
            total_count=len(rows),
            kept_count=len(kept_rows),
            excluded_count=len(rows) - len(kept_rows),
            reason_counts=reason_counts,
        ),
    )


@router.get("/dashboard/big-matches", response_model=DashboardBigMatchesOut)
def get_dashboard_big_matches(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=20),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_big_matches(as_of=as_of, limit=limit)
    items = []
    eligible_rows = [row for row in rows if _is_cutoff_eligible_row(row)]
    for row in eligible_rows:
        source_meta = _derive_source_meta(row)
        title, canonical_title, article_title = _normalize_title_fields(
            canonical_title=row.get("canonical_title"),
            article_title=row.get("article_title"),
            fallback_title=row["title"],
        )
        items.append(
            BigMatchPoint(
                matchup_id=row["matchup_id"],
                title=title,
                canonical_title=canonical_title,
                article_title=article_title,
                survey_end_date=row.get("survey_end_date"),
                value_mid=row.get("value_mid"),
                spread=row.get("spread"),
                audience_scope=row.get("audience_scope"),
                audience_region_code=row.get("audience_region_code"),
                source_priority=source_meta["source_priority"],
                official_release_at=source_meta["official_release_at"],
                article_published_at=source_meta["article_published_at"],
                freshness_hours=source_meta["freshness_hours"],
                is_official_confirmed=source_meta["is_official_confirmed"],
                source_channel=row.get("source_channel"),
                source_channels=row.get("source_channels") or [],
                source_trace=_build_source_trace(row=row, source_meta=source_meta),
            )
        )
    return DashboardBigMatchesOut(
        as_of=as_of,
        items=items,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(eligible_rows)),
    )


@router.get("/dashboard/quality", response_model=DashboardQualityOut)
def get_dashboard_quality(repo=Depends(get_repository)):
    metrics = repo.fetch_dashboard_quality()
    return DashboardQualityOut(
        generated_at=datetime.now(timezone.utc),
        quality_status=metrics["quality_status"],
        freshness_p50_hours=metrics["freshness_p50_hours"],
        freshness_p90_hours=metrics["freshness_p90_hours"],
        official_confirmed_ratio=metrics["official_confirmed_ratio"],
        needs_manual_review_count=metrics["needs_manual_review_count"],
        source_channel_mix=SourceChannelMixOut(
            article_ratio=metrics["source_channel_mix"]["article_ratio"],
            nesdc_ratio=metrics["source_channel_mix"]["nesdc_ratio"],
        ),
        freshness=DashboardQualityFreshnessOut(
            p50_hours=metrics["freshness"]["p50_hours"],
            p90_hours=metrics["freshness"]["p90_hours"],
            over_24h_ratio=metrics["freshness"]["over_24h_ratio"],
            over_48h_ratio=metrics["freshness"]["over_48h_ratio"],
            status=metrics["freshness"]["status"],
        ),
        official_confirmation=DashboardQualityOfficialOut(
            confirmed_ratio=metrics["official_confirmation"]["confirmed_ratio"],
            unconfirmed_count=metrics["official_confirmation"]["unconfirmed_count"],
            status=metrics["official_confirmation"]["status"],
        ),
        review_queue=DashboardQualityReviewOut(
            pending_count=metrics["review_queue"]["pending_count"],
            in_progress_count=metrics["review_queue"]["in_progress_count"],
            pending_over_24h_count=metrics["review_queue"]["pending_over_24h_count"],
        ),
    )


@router.get("/regions/search", response_model=list[RegionOut])
def search_regions(
    request: Request,
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    has_data: bool | None = Query(default=None),
    repo=Depends(get_repository),
):
    query_fallback = request.query_params.get("query")
    resolved_query = _normalize_region_query(q or query_fallback or "")
    region_normalized = normalize_region_code_input(resolved_query)
    if resolved_query and region_normalized.canonical:
        if region_normalized.was_aliased:
            logger.info(
                "region_code_alias_normalized endpoint=regions.search raw=%s canonical=%s",
                resolved_query,
                region_normalized.canonical,
            )
        rows = repo.search_regions_by_code(region_code=region_normalized.canonical, limit=limit, has_data=has_data)
    else:
        rows = repo.search_regions(query=resolved_query, limit=limit, has_data=has_data)
    return [RegionOut(**row) for row in rows]


@router.get("/regions/{region_code}/elections", response_model=list[RegionElectionOut])
def get_region_elections(
    region_code: str,
    topology: Literal["official", "scenario"] = Query(default="official"),
    version_id: str | None = Query(default=None),
    repo=Depends(get_repository),
):
    region_normalized = normalize_region_code_input(region_code)
    resolved_region_code = region_normalized.canonical or region_code
    if region_normalized.was_aliased and region_normalized.canonical:
        logger.info(
            "region_code_alias_normalized endpoint=regions.elections raw=%s canonical=%s",
            region_code,
            region_normalized.canonical,
        )
    rows = repo.fetch_region_elections(region_code=resolved_region_code, topology=topology, version_id=version_id)
    return [RegionElectionOut(**row) for row in rows]


@router.get("/matchups/{matchup_id}", response_model=MatchupOut)
def get_matchup(matchup_id: str, repo=Depends(get_repository)):
    resolved_matchup_id = _normalize_matchup_id(matchup_id)
    matchup = repo.get_matchup(resolved_matchup_id)
    if not matchup:
        raise HTTPException(status_code=404, detail="matchup not found")
    if not _is_cutoff_eligible_row(matchup):
        raise HTTPException(status_code=404, detail="matchup not found")
    source_meta = _derive_source_meta(matchup)
    payload = dict(matchup)
    payload.update(source_meta)
    title, canonical_title, article_title = _normalize_title_fields(
        canonical_title=payload.get("canonical_title"),
        article_title=payload.get("article_title"),
        fallback_title=payload.get("title") or payload.get("matchup_id") or "",
    )
    payload["title"] = title
    payload["canonical_title"] = canonical_title
    payload["article_title"] = article_title
    payload["source_trace"] = _build_source_trace(row=payload, source_meta=source_meta)
    return MatchupOut(**payload)


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: str,
    repo=Depends(get_repository),
    data_go_service=Depends(get_candidate_data_go_service),
):
    candidate = repo.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate not found")
    base_row = dict(candidate)
    enriched = data_go_service.enrich_candidate(dict(candidate))
    source_meta = _derive_source_meta(enriched)
    payload = dict(enriched)
    payload["name_ko"] = _normalize_candidate_text(payload.get("name_ko"))
    placeholder_name_applied = False
    if not payload.get("name_ko"):
        payload["name_ko"] = candidate_id
        placeholder_name_applied = True
    payload["party_name"] = _normalize_candidate_text(payload.get("party_name"))
    payload["job"] = _normalize_candidate_text(payload.get("job"))
    payload["career_summary"] = _normalize_candidate_text(payload.get("career_summary"))
    payload["election_history"] = _normalize_candidate_text(payload.get("election_history"))
    payload["gender"] = _normalize_candidate_text(payload.get("gender"))

    profile_provenance = _build_candidate_profile_provenance(base_row=base_row, final_row=payload)
    payload.update(source_meta)
    payload["source_channels"] = payload.get("source_channels") or []
    payload["profile_provenance"] = profile_provenance
    payload["profile_source"] = _derive_candidate_profile_source(profile_provenance)
    payload["profile_completeness"] = _derive_candidate_profile_completeness(payload)
    payload["profile_source_type"] = _normalize_candidate_text(payload.get("profile_source_type"))
    payload["profile_source_url"] = _normalize_candidate_text(payload.get("profile_source_url"))
    payload["placeholder_name_applied"] = placeholder_name_applied
    return CandidateOut(**payload)


@router.get("/ops/metrics/summary", response_model=OpsMetricsSummaryOut)
def get_ops_metrics_summary(
    window_hours: int = Query(default=24, ge=1, le=24 * 14),
    repo=Depends(get_repository),
):
    ingestion = repo.fetch_ops_ingestion_metrics(window_hours=window_hours)
    review = repo.fetch_ops_review_metrics(window_hours=window_hours)
    failure_distribution = repo.fetch_ops_failure_distribution(window_hours=window_hours)

    warnings = [
        {
            "rule_key": "fetch_fail_rate",
            "description": "ingestion fetch_fail_rate > 0.15",
            "threshold": 0.15,
            "actual": float(ingestion["fetch_fail_rate"]),
            "triggered": float(ingestion["fetch_fail_rate"]) > 0.15,
        },
        {
            "rule_key": "mapping_error_spike_24h",
            "description": "review_queue mapping_error in last window >= 5",
            "threshold": 5.0,
            "actual": float(review["mapping_error_24h_count"]),
            "triggered": int(review["mapping_error_24h_count"]) >= 5,
        },
        {
            "rule_key": "pending_queue_backlog_24h",
            "description": "pending review items older than 24h >= 10",
            "threshold": 10.0,
            "actual": float(review["pending_over_24h_count"]),
            "triggered": int(review["pending_over_24h_count"]) >= 10,
        },
    ]

    return OpsMetricsSummaryOut(
        generated_at=datetime.now(timezone.utc),
        window_hours=window_hours,
        ingestion=OpsIngestionMetricsOut(**ingestion),
        review_queue=OpsReviewMetricsOut(**review),
        failure_distribution=[OpsFailureDistributionOut(**x) for x in failure_distribution],
        warnings=[OpsWarningRuleOut(**x) for x in warnings],
    )


@router.get("/ops/coverage/summary", response_model=OpsCoverageSummaryOut)
def get_ops_coverage_summary(repo=Depends(get_repository)):
    summary = repo.fetch_ops_coverage_summary()
    return OpsCoverageSummaryOut(
        generated_at=datetime.now(timezone.utc),
        state=summary["state"],
        warning_message=summary["warning_message"],
        regions_total=summary["regions_total"],
        regions_covered=summary["regions_covered"],
        sido_covered=summary["sido_covered"],
        observations_total=summary["observations_total"],
        latest_survey_end_date=summary["latest_survey_end_date"],
    )


@router.get("/review-queue/items", response_model=list[ReviewQueueItemOut])
def get_review_queue_items(
    status: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo=Depends(get_repository),
):
    rows = repo.fetch_review_queue_items(
        status=status,
        issue_type=issue_type,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [ReviewQueueItemOut(**row) for row in rows]


def _apply_review_queue_decision(
    *,
    item_id: int,
    decision_status: str,
    decision: ReviewQueueDecisionIn,
    repo,
):
    row = repo.update_review_queue_status(
        item_id=item_id,
        status=decision_status,
        assigned_to=decision.assigned_to,
        review_note=decision.review_note,
    )
    if not row:
        raise HTTPException(status_code=404, detail="review queue item not found")
    return ReviewQueueItemOut(**row)


@router.post("/review/{item_id}/approve", response_model=ReviewQueueItemOut)
def approve_review_item(
    item_id: int,
    decision: ReviewQueueDecisionIn,
    _=Depends(require_internal_job_token),
    repo=Depends(get_repository),
):
    return _apply_review_queue_decision(
        item_id=item_id,
        decision_status="approved",
        decision=decision,
        repo=repo,
    )


@router.post("/review/{item_id}/reject", response_model=ReviewQueueItemOut)
def reject_review_item(
    item_id: int,
    decision: ReviewQueueDecisionIn,
    _=Depends(require_internal_job_token),
    repo=Depends(get_repository),
):
    return _apply_review_queue_decision(
        item_id=item_id,
        decision_status="rejected",
        decision=decision,
        repo=repo,
    )


@router.get("/review-queue/stats", response_model=ReviewQueueStatsOut)
def get_review_queue_stats(
    window_hours: int = Query(default=24, ge=1, le=24 * 14),
    repo=Depends(get_repository),
):
    stats = repo.fetch_review_queue_stats(window_hours=window_hours)
    return ReviewQueueStatsOut(
        generated_at=datetime.now(timezone.utc),
        window_hours=window_hours,
        total_count=stats["total_count"],
        pending_count=stats["pending_count"],
        in_progress_count=stats["in_progress_count"],
        resolved_count=stats["resolved_count"],
        issue_type_counts=[ReviewQueueIssueCountOut(**x) for x in stats["issue_type_counts"]],
        error_code_counts=[ReviewQueueErrorCountOut(**x) for x in stats["error_code_counts"]],
    )


@router.get("/review-queue/trends", response_model=ReviewQueueTrendsOut)
def get_review_queue_trends(
    window_hours: int = Query(default=24, ge=1, le=24 * 14),
    bucket_hours: int = Query(default=6, ge=1, le=24),
    issue_type: str | None = Query(default=None),
    error_code: str | None = Query(default=None),
    repo=Depends(get_repository),
):
    rows = repo.fetch_review_queue_trends(
        window_hours=window_hours,
        bucket_hours=bucket_hours,
        issue_type=issue_type,
        error_code=error_code,
    )
    return ReviewQueueTrendsOut(
        generated_at=datetime.now(timezone.utc),
        window_hours=window_hours,
        bucket_hours=bucket_hours,
        points=[ReviewQueueTrendPointOut(**x) for x in rows],
    )


@router.post("/jobs/run-ingest", response_model=JobRunOut)
async def run_ingest_job(
    request: Request,
    _=Depends(require_internal_job_token),
    repo=Depends(get_repository),
):
    try:
        raw_payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid json payload: {exc}") from exc
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=422, detail="payload must be a JSON object")

    normalized_payload = normalize_ingest_payload(raw_payload)
    try:
        payload = IngestPayload.model_validate(normalized_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    result = ingest_payload(payload, repo)
    return JobRunOut(
        run_id=result.run_id,
        processed_count=result.processed_count,
        error_count=result.error_count,
        status=result.status,
    )
