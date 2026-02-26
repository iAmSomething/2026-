from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when DB settings are missing or invalid."""


class DatabaseConnectionError(RuntimeError):
    """Raised when a DB connection cannot be established."""


@contextmanager
def get_connection():
    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        raise DatabaseConfigurationError("database settings are not configured") from exc

    database_url = str(settings.database_url or "").strip()
    if not database_url:
        raise DatabaseConfigurationError("DATABASE_URL is empty")

    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
    except psycopg.Error as exc:
        raise DatabaseConnectionError("database connection failed") from exc

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
