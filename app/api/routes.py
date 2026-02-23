from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

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
from app.services.ingest_service import ingest_payload

router = APIRouter(prefix="/api/v1", tags=["v1"])

MATCHUP_ID_ALIASES = {
    "m_2026_seoul_mayor": "20260603|광역자치단체장|11-000",
}


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


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    as_of: date | None = Query(default=None),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_summary(as_of=as_of)
    party_support = []
    presidential_approval = []

    for row in rows:
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
        elif row["option_type"] == "presidential_approval":
            presidential_approval.append(point)

    return DashboardSummaryOut(
        as_of=as_of,
        party_support=party_support,
        presidential_approval=presidential_approval,
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(rows)),
    )


@router.get("/dashboard/map-latest", response_model=DashboardMapLatestOut)
def get_dashboard_map_latest(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_map_latest(as_of=as_of, limit=limit)
    items = []
    for row in rows:
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
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(rows)),
    )


@router.get("/dashboard/big-matches", response_model=DashboardBigMatchesOut)
def get_dashboard_big_matches(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=20),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_big_matches(as_of=as_of, limit=limit)
    items = []
    for row in rows:
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
        scope_breakdown=ScopeBreakdownOut(**_build_scope_breakdown(rows)),
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
    resolved_query = q or query_fallback
    if not resolved_query:
        raise HTTPException(status_code=422, detail="q or query is required")

    rows = repo.search_regions(query=resolved_query, limit=limit)
    return [RegionOut(**row) for row in rows]


@router.get("/regions/{region_code}/elections", response_model=list[RegionElectionOut])
def get_region_elections(region_code: str, repo=Depends(get_repository)):
    rows = repo.fetch_region_elections(region_code=region_code)
    return [RegionElectionOut(**row) for row in rows]


@router.get("/matchups/{matchup_id}", response_model=MatchupOut)
def get_matchup(matchup_id: str, repo=Depends(get_repository)):
    resolved_matchup_id = MATCHUP_ID_ALIASES.get(matchup_id, matchup_id)
    matchup = repo.get_matchup(resolved_matchup_id)
    if not matchup:
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
def run_ingest_job(
    payload: IngestPayload,
    _=Depends(require_internal_job_token),
    repo=Depends(get_repository),
):
    result = ingest_payload(payload, repo)
    return JobRunOut(
        run_id=result.run_id,
        processed_count=result.processed_count,
        error_count=result.error_count,
        status=result.status,
    )
