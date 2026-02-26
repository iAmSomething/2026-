from pathlib import Path


def test_schema_contains_region_topology_tables_and_seed() -> None:
    sql = Path("db/schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS region_topology_versions" in sql
    assert "region_topology_versions_mode_check" in sql
    assert "region_topology_versions_status_check" in sql
    assert "CREATE TABLE IF NOT EXISTS region_topology_edges" in sql
    assert "idx_region_topology_edges_child" in sql
    assert "idx_region_topology_edges_parent" in sql
    assert "scenario-gj-jn-merge-v1" in sql
