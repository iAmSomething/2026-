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
    SummaryPoint,
)
from app.services.cutoff_policy import has_article_source, is_article_published_at_allowed
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


def _is_cutoff_eligible_row(row: dict) -> bool:
    if not has_article_source(
        source_channel=row.get("source_channel"),
        source_channels=row.get("source_channels"),
    ):
        return True
    return is_article_published_at_allowed(row.get("article_published_at"))


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


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    as_of: date | None = Query(default=None),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_summary(as_of=as_of)
    party_support = []
    president_job_approval = []
    election_frame = []
    eligible_rows = [row for row in rows if _is_cutoff_eligible_row(row)]

    for row in eligible_rows:
        if row.get("audience_scope") != "national":
            continue
        source_meta = _derive_source_meta(row)
        point = SummaryPoint(
            option_name=row["option_name"],
            value_mid=row["value_mid"],
            pollster=row["pollster"],
            survey_end_date=row["survey_end_date"],
            audience_scope=row.get("audience_scope"),
            audience_region_code=row.get("audience_region_code"),
            source_priority=source_meta["source_priority"],
            official_release_at=source_meta["official_release_at"],
            article_published_at=source_meta["article_published_at"],
            freshness_hours=source_meta["freshness_hours"],
            is_official_confirmed=source_meta["is_official_confirmed"],
            source_channel=row.get("source_channel"),
            source_channels=row.get("source_channels") or [],
            verified=row["verified"],
        )
        if row["option_type"] == "party_support":
            party_support.append(point)
        elif row["option_type"] == "president_job_approval":
            president_job_approval.append(point)
        elif row["option_type"] == "election_frame":
            election_frame.append(point)
        elif row["option_type"] == "presidential_approval":
            bucket = _classify_presidential_option(point.option_name)
            if bucket == "president_job_approval":
                president_job_approval.append(point)
            else:
                election_frame.append(point)

    deprecated_presidential_approval = list(president_job_approval)

    return DashboardSummaryOut(
        as_of=as_of,
        data_source=_derive_dashboard_data_source(eligible_rows),
        party_support=party_support,
        president_job_approval=president_job_approval,
        election_frame=election_frame,
        presidential_approval=deprecated_presidential_approval,
        presidential_approval_deprecated=True,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(eligible_rows)),
    )


@router.get("/dashboard/map-latest", response_model=DashboardMapLatestOut)
def get_dashboard_map_latest(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_map_latest(as_of=as_of, limit=limit)
    items = []
    eligible_rows = [row for row in rows if _is_cutoff_eligible_row(row)]
    for row in eligible_rows:
        source_meta = _derive_source_meta(row)
        items.append(
            MapLatestPoint(
                region_code=row["region_code"],
                office_type=row["office_type"],
                title=row["title"],
                value_mid=row.get("value_mid"),
                survey_end_date=row.get("survey_end_date"),
                option_name=row.get("option_name"),
                audience_scope=row.get("audience_scope"),
                audience_region_code=row.get("audience_region_code"),
                source_priority=source_meta["source_priority"],
                official_release_at=source_meta["official_release_at"],
                article_published_at=source_meta["article_published_at"],
                freshness_hours=source_meta["freshness_hours"],
                is_official_confirmed=source_meta["is_official_confirmed"],
                source_channel=row.get("source_channel"),
                source_channels=row.get("source_channels") or [],
            )
        )
    return DashboardMapLatestOut(
        as_of=as_of,
        items=items,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(eligible_rows)),
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
        items.append(
            BigMatchPoint(
                matchup_id=row["matchup_id"],
                title=row["title"],
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
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    repo=Depends(get_repository),
):
    query_fallback = request.query_params.get("query")
    resolved_query = _normalize_region_query(q or query_fallback or "")
    if not resolved_query:
        raise HTTPException(status_code=422, detail="q or query is required")

    region_normalized = normalize_region_code_input(resolved_query)
    if region_normalized.canonical:
        if region_normalized.was_aliased:
            logger.info(
                "region_code_alias_normalized endpoint=regions.search raw=%s canonical=%s",
                resolved_query,
                region_normalized.canonical,
            )
        rows = repo.search_regions_by_code(region_code=region_normalized.canonical, limit=limit)
    else:
        rows = repo.search_regions(query=resolved_query, limit=limit)
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
    enriched = data_go_service.enrich_candidate(dict(candidate))
    source_meta = _derive_source_meta(enriched)
    payload = dict(enriched)
    payload.update(source_meta)
    payload["source_channels"] = payload.get("source_channels") or []
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
