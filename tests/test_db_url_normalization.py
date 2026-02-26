import pytest

from app.db import _normalize_database_url


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
