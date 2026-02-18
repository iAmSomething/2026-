from pathlib import Path
import sys
import os

import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import run_schema


def preflight_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        if os.getenv("CI", "").lower() in {"1", "true", "yes"}:
            fallback = "postgresql://postgres:postgres@127.0.0.1:5432/app"
            os.environ["DATABASE_URL"] = fallback
            print("[WARN] DATABASE_URL is empty. Fallback to CI postgres service URL.")
            database_url = fallback
        else:
            raise SystemExit(
                "[FAIL] DATABASE_URL is empty.\n"
                "Guide:\n"
                "1) Set .env or shell env DATABASE_URL\n"
                "2) Example: postgresql://user:pass@127.0.0.1:5432/app\n"
                "3) Re-run: python scripts/init_db.py"
            )
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("[FAIL] DATABASE_URL must be a PostgreSQL URI (postgresql://...)")
    return database_url


if __name__ == "__main__":
    preflight_database_url()
    try:
        run_schema(ROOT / "db" / "schema.sql")
    except psycopg.OperationalError as exc:
        raise SystemExit(
            "[FAIL] DB connection failed while applying schema.\n"
            f"Cause: {exc.__class__.__name__}: {exc}\n"
            "Guide:\n"
            "1) Verify DATABASE_URL host/password/reachability\n"
            "2) On GitHub Actions staging-smoke, confirm postgres service health and DATABASE_URL resolution step\n"
            "3) Re-run after fixing connection settings"
        ) from exc
    print("schema applied")
