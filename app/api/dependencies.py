from functools import lru_cache
from secrets import compare_digest

from fastapi import Depends, Header, HTTPException

from app.config import get_settings

from app.db import get_connection
from app.services.data_go_candidate import DataGoCandidateConfig, DataGoCandidateService
from app.services.repository import PostgresRepository


def get_repository():
    with get_connection() as conn:
        yield PostgresRepository(conn)


@lru_cache(maxsize=1)
def get_candidate_data_go_service() -> DataGoCandidateService:
    try:
        settings = get_settings()
        cfg = DataGoCandidateConfig(
            endpoint_url=settings.data_go_candidate_endpoint_url,
            service_key=settings.data_go_kr_key,
            sg_id=settings.data_go_candidate_sg_id,
            sg_typecode=settings.data_go_candidate_sg_typecode,
            sd_name=settings.data_go_candidate_sd_name,
            sgg_name=settings.data_go_candidate_sgg_name,
            timeout_sec=settings.data_go_candidate_timeout_sec,
            max_retries=settings.data_go_candidate_max_retries,
            cache_ttl_sec=settings.data_go_candidate_cache_ttl_sec,
            requests_per_sec=settings.data_go_candidate_requests_per_sec,
            num_of_rows=settings.data_go_candidate_num_of_rows,
        )
    except Exception:  # noqa: BLE001
        cfg = DataGoCandidateConfig(endpoint_url="", service_key=None, sg_id=None, sg_typecode=None)
    return DataGoCandidateService(cfg)


def require_internal_job_token(
    authorization: str | None = Header(default=None),
):
    settings = get_settings()
    expected = settings.internal_job_token
    if not expected:
        raise HTTPException(status_code=503, detail="internal job token is not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="invalid bearer token")
