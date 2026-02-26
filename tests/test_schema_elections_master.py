from pathlib import Path


def test_schema_contains_elections_master_table() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS elections" in sql
    assert "slot_matchup_id TEXT NOT NULL" in sql
    assert "has_poll_data BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "latest_matchup_id TEXT NULL" in sql
    assert "elections_source_check" in sql
