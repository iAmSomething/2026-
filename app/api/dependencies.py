from secrets import compare_digest

from fastapi import Depends, Header, HTTPException

from app.config import get_settings

from app.db import get_connection
from app.services.repository import PostgresRepository


def get_repository():
    with get_connection() as conn:
        yield PostgresRepository(conn)


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
