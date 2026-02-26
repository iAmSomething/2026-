from pathlib import Path


def test_schema_contains_party_inference_columns() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "party_inferred BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "party_inference_source TEXT NULL" in sql
    assert "party_inference_confidence FLOAT NULL" in sql
    assert "candidate_verified BOOLEAN NOT NULL DEFAULT TRUE" in sql
    assert "candidate_verify_source TEXT NULL" in sql
    assert "candidate_verify_confidence FLOAT NULL" in sql
    assert "needs_manual_review BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "ALTER TABLE candidates" in sql
    assert "ADD COLUMN IF NOT EXISTS source_channel TEXT NULL" in sql
    assert "ADD COLUMN IF NOT EXISTS source_channels TEXT[] NULL" in sql
    assert "candidates_party_inference_source_check" in sql
    assert "ALTER TABLE poll_options" in sql
    assert "ADD COLUMN IF NOT EXISTS party_inferred BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "poll_options_party_inference_source_check" in sql
    assert "poll_options_candidate_verify_source_check" in sql
