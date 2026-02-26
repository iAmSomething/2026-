from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from app.db import run_schema

_TRUTHY = {"1", "true", "yes", "y", "on"}
_FALSY = {"0", "false", "no", "n", "off"}
_SCHEMA_MISMATCH_SQLSTATE = {"42P01", "42703"}  # undefined_table, undefined_column

_schema_heal_lock = Lock()
_schema_healed_once = False

DB_BOOTSTRAP_STATE: dict[str, object] = {
    "enabled": False,
    "attempted": False,
    "ok": None,
    "detail": None,
}


def _parse_bool_env(value: str | None) -> bool | None:
    if value is None:
        return None
    token = value.strip().lower()
    if token in _TRUTHY:
        return True
    if token in _FALSY:
        return False
    return None


def should_auto_apply_schema_on_startup() -> bool:
    explicit = _parse_bool_env(os.getenv("AUTO_APPLY_SCHEMA_ON_STARTUP"))
    if explicit is not None:
        return explicit
    return bool(os.getenv("RAILWAY_PROJECT_ID") or os.getenv("RAILWAY_SERVICE_ID"))


def apply_schema_bootstrap() -> dict[str, object]:
    enabled = should_auto_apply_schema_on_startup()
    DB_BOOTSTRAP_STATE["enabled"] = enabled
    if not enabled:
        DB_BOOTSTRAP_STATE["attempted"] = False
        DB_BOOTSTRAP_STATE["ok"] = None
        DB_BOOTSTRAP_STATE["detail"] = "disabled"
        return DB_BOOTSTRAP_STATE

    DB_BOOTSTRAP_STATE["attempted"] = True
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    try:
        run_schema(schema_path)
    except Exception as exc:  # noqa: BLE001
        DB_BOOTSTRAP_STATE["ok"] = False
        DB_BOOTSTRAP_STATE["detail"] = f"{type(exc).__name__}: {exc}"
        return DB_BOOTSTRAP_STATE

    DB_BOOTSTRAP_STATE["ok"] = True
    DB_BOOTSTRAP_STATE["detail"] = "schema applied"
    return DB_BOOTSTRAP_STATE


def is_schema_mismatch_sqlstate(sqlstate: str | None) -> bool:
    return sqlstate in _SCHEMA_MISMATCH_SQLSTATE


def heal_schema_once() -> bool:
    global _schema_healed_once  # noqa: PLW0603

    with _schema_heal_lock:
        if _schema_healed_once:
            return False
        schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
        run_schema(schema_path)
        _schema_healed_once = True
        return True
