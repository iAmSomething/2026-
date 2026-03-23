from pathlib import Path


def test_schema_contains_incumbent_registry_table() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS incumbent_registry" in sql
    assert "UNIQUE (region_code, office_type)" in sql
    assert "term_limit_flag BOOLEAN" in sql
    assert "needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "source_channel TEXT NOT NULL DEFAULT 'incumbent_registry'" in sql
    assert "incumbent_registry_source_channel_check" in sql
    assert "idx_incumbent_registry_region_office" in sql
