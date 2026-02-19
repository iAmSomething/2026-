from pathlib import Path


def test_schema_contains_party_inference_columns() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "party_inferred BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "party_inference_source TEXT NULL" in sql
    assert "party_inference_confidence FLOAT NULL" in sql
    assert "needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "ALTER TABLE candidates" in sql
    assert "ADD COLUMN IF NOT EXISTS needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "ALTER TABLE poll_options" in sql
    assert "ADD COLUMN IF NOT EXISTS party_inferred BOOLEAN NOT NULL DEFAULT FALSE" in sql
