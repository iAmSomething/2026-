from pathlib import Path


def test_schema_contains_legal_metadata_columns_and_backfill():
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "confidence_level FLOAT NULL" in sql
    assert "date_inference_mode TEXT NULL" in sql
    assert "date_inference_confidence FLOAT NULL" in sql
    assert "audience_scope TEXT NULL" in sql
    assert "audience_region_code TEXT NULL" in sql
    assert "source_channels TEXT[] NULL" in sql
    assert "date_inference_failed_count INT NOT NULL DEFAULT 0" in sql
    assert "date_inference_estimated_count INT NOT NULL DEFAULT 0" in sql
    assert "UPDATE poll_observations" in sql
    assert "SET source_channels = ARRAY[source_channel]" in sql
