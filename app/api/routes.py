from datetime import date

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
