import pytest

from app.db import _classify_connection_error, _normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://postgres.ref:plainpass@aws-1.pooler.supabase.com:5432/postgres",
            "postgresql://postgres.ref:plainpass@aws-1.pooler.supabase.com:5432/postgres",
        ),
        (
            "postgresql://postgres.ref:pa!ss@aws-1.pooler.supabase.com:5432/postgres",
            "postgresql://postgres.ref:pa%21ss@aws-1.pooler.supabase.com:5432/postgres",
        ),
        (
            "postgresql://postgres.ref:pa@ss@aws-1.pooler.supabase.com:5432/postgres",
            "postgresql://postgres.ref:pa%40ss@aws-1.pooler.supabase.com:5432/postgres",
        ),
        (
            "postgresql://postgres.ref:pa%40ss@aws-1.pooler.supabase.com:5432/postgres",
            "postgresql://postgres.ref:pa%40ss@aws-1.pooler.supabase.com:5432/postgres",
        ),
        ("", ""),
    ],
)
def test_normalize_database_url(raw: str, expected: str):
    assert _normalize_database_url(raw) == expected


class _FakePsycopgError(Exception):
    def __init__(self, message: str, sqlstate: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_FakePsycopgError("password authentication failed", "28P01"), "auth_failed"),
        (_FakePsycopgError("role is not permitted", "28000"), "auth_error"),
        (_FakePsycopgError("could not translate host name \"bad\" to address"), "invalid_host_or_uri"),
        (_FakePsycopgError("connection refused"), "connection_refused"),
        (_FakePsycopgError("timeout expired"), "network_timeout"),
        (_FakePsycopgError("sslmode value \"disable\" invalid when SSL required"), "ssl_required"),
        (_FakePsycopgError("some other message"), "unknown"),
    ],
)
def test_classify_connection_error(error, expected):  # noqa: ANN001
    assert _classify_connection_error(error) == expected
