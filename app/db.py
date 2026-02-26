from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, unquote

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when DB settings are missing or invalid."""


class DatabaseConnectionError(RuntimeError):
    """Raised when a DB connection cannot be established."""


def _classify_connection_error(exc: psycopg.Error) -> str:
    sqlstate = str(getattr(exc, "sqlstate", "") or "").upper()
    if sqlstate == "28P01":
        return "auth_failed"
    if sqlstate.startswith("28"):
        return "auth_error"
    if sqlstate in {"08001", "08006"}:
        return "network_error"

    message = str(exc).lower()
    if "could not translate host name" in message:
        return "invalid_host_or_uri"
    if "connection refused" in message:
        return "connection_refused"
    if "timeout expired" in message or "timed out" in message:
        return "network_timeout"
    if "sslmode" in message or ("ssl" in message and "required" in message):
        return "ssl_required"
    return "unknown"


def _normalize_database_url(database_url: str) -> str:
    text = str(database_url or "").strip()
    if not text:
        return text
    if "://" not in text or "@" not in text:
        return text

    scheme, remainder = text.split("://", 1)
    if not scheme.startswith("postgres"):
        return text
    if "@" not in remainder or ":" not in remainder:
        return text

    credentials, tail = remainder.rsplit("@", 1)
    if ":" not in credentials:
        return text

    username, raw_password = credentials.split(":", 1)
    if not username:
        return text

    normalized_password = quote(unquote(raw_password), safe="")
    return f"{scheme}://{username}:{normalized_password}@{tail}"


@contextmanager
def get_connection():
    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        raise DatabaseConfigurationError("database settings are not configured") from exc

    database_url = _normalize_database_url(str(settings.database_url or "").strip())
    if not database_url:
        raise DatabaseConfigurationError("DATABASE_URL is empty")

    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
    except psycopg.Error as exc:
        reason = _classify_connection_error(exc)
        raise DatabaseConnectionError(f"database connection failed ({reason})") from exc

    try:
        yield conn
    finally:
        conn.close()


def run_schema(schema_path: str | Path) -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
