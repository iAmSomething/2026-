from pathlib import Path


def test_schema_contains_read_performance_indexes() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "idx_poll_observations_matchup_latest" in sql
    assert "ON poll_observations (matchup_id, survey_end_date DESC, id DESC)" in sql
    assert "idx_poll_observations_verified_region_office_date" in sql
    assert "ON poll_observations (region_code, office_type, survey_end_date DESC, id DESC)" in sql
    assert "idx_poll_options_observation_value" in sql
    assert "ON poll_options (observation_id, value_mid DESC, option_name)" in sql
    assert "idx_poll_options_summary_type_observation" in sql
    assert "idx_poll_options_candidate_matchup_observation_value" in sql
    assert "idx_review_queue_entity_status" in sql
    assert "ON review_queue (entity_type, entity_id, status)" in sql
