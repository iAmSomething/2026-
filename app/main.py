import os
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg

from app.api.routes import router as api_router
from app.db import DatabaseConfigurationError, DatabaseConnectionError, get_connection
from app.runtime_db_guard import DB_BOOTSTRAP_STATE, apply_schema_bootstrap, heal_schema_once, is_schema_mismatch_sqlstate

DEFAULT_CORS_ALLOW_ORIGINS = (
    "https://2026-deploy.vercel.app,"
    "http://127.0.0.1:3000,"
    "http://localhost:3000,"
    "http://127.0.0.1:3300,"
    "http://localhost:3300"
)

logger = logging.getLogger(__name__)


def _resolve_cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="Election 2026 Backend MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.on_event("startup")
def startup_schema_bootstrap():
    state = apply_schema_bootstrap()
    logger.info(
        "startup_schema_bootstrap enabled=%s attempted=%s ok=%s detail=%s",
        state.get("enabled"),
        state.get("attempted"),
        state.get("ok"),
        state.get("detail"),
    )


@app.exception_handler(psycopg.Error)
def handle_psycopg_error(_, exc: psycopg.Error):  # noqa: ANN001
    detail = "database query failed"
    sqlstate = getattr(exc, "sqlstate", None)

    if is_schema_mismatch_sqlstate(sqlstate):
        try:
            healed = heal_schema_once()
        except Exception as heal_exc:  # noqa: BLE001
            logger.exception("schema_auto_heal_failed: %s", heal_exc)
            healed = False
        if healed:
            detail = "database schema auto-healed; retry request"
        else:
            detail = "database schema mismatch detected"
    elif sqlstate:
        detail = f"database query failed ({sqlstate})"

    return JSONResponse(status_code=503, content={"detail": detail})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def health_db_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone() or {}
    except DatabaseConfigurationError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "db": "error",
                "reason": "database_not_configured",
                "detail": str(exc),
                "bootstrap": DB_BOOTSTRAP_STATE,
            },
        )
    except DatabaseConnectionError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "db": "error",
                "reason": "database_connection_failed",
                "detail": str(exc),
                "bootstrap": DB_BOOTSTRAP_STATE,
            },
        )
    except psycopg.Error as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "db": "error",
                "reason": "database_query_failed",
                "sqlstate": exc.sqlstate,
                "bootstrap": DB_BOOTSTRAP_STATE,
            },
        )

    return {
        "status": "ok",
        "db": "ok",
        "ping": row.get("ok") == 1,
        "bootstrap": DB_BOOTSTRAP_STATE,
    }
