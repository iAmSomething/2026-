from __future__ import annotations

from pathlib import Path

from scripts.sync_elections_master import run_elections_master_sync


def test_run_elections_master_sync_dry_run_writes_report(monkeypatch, tmp_path: Path) -> None:
    captured_upserts: list[dict] = []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    class _FakeRepo:
        def __init__(self, conn):  # noqa: ARG002
            pass

        def fetch_all_regions(self):
            return [
                {
                    "region_code": "32-000",
                    "sido_name": "강원특별자치도",
                    "sigungu_name": "전체",
                    "admin_level": "sido",
                },
                {
                    "region_code": "26-710",
                    "sido_name": "부산광역시",
                    "sigungu_name": "부산진구",
                    "admin_level": "sigungu",
                },
            ]

        def fetch_latest_matchup_ids_by_region_office(self):
            return {("32-000", "광역자치단체장"): "20260603|광역자치단체장|32-000"}

        def fetch_observed_byelection_pairs(self):
            return {("26-710", "기초자치단체장 재보궐")}

        def upsert_election_slot(self, election_slot):
            captured_upserts.append(election_slot)

        def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):  # noqa: ARG002
            return None

    monkeypatch.setattr("scripts.sync_elections_master.get_connection", lambda: _FakeConn())
    monkeypatch.setattr("scripts.sync_elections_master.PostgresRepository", _FakeRepo)

    report_path = tmp_path / "report.json"
    report = run_elections_master_sync(dry_run=True, report_path=str(report_path))

    assert report["status"] == "success"
    assert report["acceptance_checks"]["default_slot_pairs_complete"] is True
    assert report["acceptance_checks"]["sample_metro_region_ge_3"] is True
    assert report["sample_checks"]["region_26_710_slot_count"] >= 2
    assert captured_upserts == []
    assert report_path.exists()
