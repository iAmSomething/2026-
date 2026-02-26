from contextlib import contextmanager

import psycopg
import pytest
from fastapi import HTTPException

import app.api.dependencies as deps


@contextmanager
def _fake_connection():
    yield object()


def _make_psycopg_error(sqlstate: str) -> psycopg.Error:
    err = psycopg.ProgrammingError("boom")
    err.sqlstate = sqlstate
    return err


def test_get_repository_schema_mismatch_triggers_heal(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(deps, "get_connection", _fake_connection)
    monkeypatch.setattr(deps, "heal_schema_once", lambda: True)

    gen = deps.get_repository()
    _ = next(gen)

    with pytest.raises(HTTPException) as exc_info:
        gen.throw(_make_psycopg_error("42P01"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "database schema auto-healed; retry request"


def test_get_repository_schema_mismatch_reports_detected_when_heal_not_applied(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(deps, "get_connection", _fake_connection)
    monkeypatch.setattr(deps, "heal_schema_once", lambda: False)

    gen = deps.get_repository()
    _ = next(gen)

    with pytest.raises(HTTPException) as exc_info:
        gen.throw(_make_psycopg_error("42703"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "database schema mismatch detected"


def test_get_repository_non_schema_db_error_keeps_sqlstate_detail(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(deps, "get_connection", _fake_connection)

    gen = deps.get_repository()
    _ = next(gen)

    with pytest.raises(HTTPException) as exc_info:
        gen.throw(_make_psycopg_error("40001"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "database query failed (40001)"
