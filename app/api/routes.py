from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_candidate_data_go_service, get_repository, require_internal_job_token
from app.models.schemas import (
    BigMatchPoint,
    CandidateOut,
    DashboardBigMatchesOut,
    DashboardMapLatestOut,
    DashboardSummaryOut,
    IngestPayload,
    JobRunOut,
    MapLatestPoint,
    MatchupOut,
    OpsFailureDistributionOut,
    OpsIngestionMetricsOut,
    OpsMetricsSummaryOut,
    OpsReviewMetricsOut,
    OpsWarningRuleOut,
    RegionElectionOut,
    RegionOut,
    SummaryPoint,
)
from app.services.ingest_service import ingest_payload

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    as_of: date | None = Query(default=None),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_summary(as_of=as_of)
    party_support = []
    presidential_approval = []

    for row in rows:
        point = SummaryPoint(
            option_name=row["option_name"],
            value_mid=row["value_mid"],
            pollster=row["pollster"],
            survey_end_date=row["survey_end_date"],
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
    )


@router.get("/dashboard/map-latest", response_model=DashboardMapLatestOut)
def get_dashboard_map_latest(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_map_latest(as_of=as_of, limit=limit)
    return DashboardMapLatestOut(as_of=as_of, items=[MapLatestPoint(**row) for row in rows])


@router.get("/dashboard/big-matches", response_model=DashboardBigMatchesOut)
def get_dashboard_big_matches(
    as_of: date | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=20),
    repo=Depends(get_repository),
):
    rows = repo.fetch_dashboard_big_matches(as_of=as_of, limit=limit)
    return DashboardBigMatchesOut(as_of=as_of, items=[BigMatchPoint(**row) for row in rows])


@router.get("/regions/search", response_model=list[RegionOut])
def search_regions(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    repo=Depends(get_repository),
):
    rows = repo.search_regions(query=q, limit=limit)
    return [RegionOut(**row) for row in rows]


@router.get("/regions/{region_code}/elections", response_model=list[RegionElectionOut])
def get_region_elections(region_code: str, repo=Depends(get_repository)):
    rows = repo.fetch_region_elections(region_code=region_code)
    return [RegionElectionOut(**row) for row in rows]


@router.get("/matchups/{matchup_id}", response_model=MatchupOut)
def get_matchup(matchup_id: str, repo=Depends(get_repository)):
    matchup = repo.get_matchup(matchup_id)
    if not matchup:
        raise HTTPException(status_code=404, detail="matchup not found")
    return MatchupOut(**matchup)


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
    return CandidateOut(**enriched)


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
