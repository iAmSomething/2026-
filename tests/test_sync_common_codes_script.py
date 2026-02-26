import json
from types import SimpleNamespace

import scripts.sync_common_codes as sync_script


def test_compute_region_diff_reports_add_update_delete_candidates():
    existing_rows = [
        {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
        {
            "region_code": "11-110",
            "sido_name": "서울특별시",
            "sigungu_name": "종로구",
            "admin_level": "sigungu",
            "parent_region_code": "11-000",
        },
    ]
    fetched_rows = [
        {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
        {
            "region_code": "11-110",
            "sido_name": "서울특별시",
            "sigungu_name": "종로구(개정)",
            "admin_level": "sigungu",
            "parent_region_code": "11-000",
        },
        {
            "region_code": "26-000",
            "sido_name": "부산광역시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        },
    ]

    diff = sync_script._compute_region_diff(existing_rows=existing_rows, fetched_rows=fetched_rows)

    assert diff["existing_total"] == 2
    assert diff["fetched_total"] == 3
    assert diff["added_count"] == 1
    assert diff["updated_count"] == 1
    assert diff["unchanged_count"] == 1
    assert diff["delete_candidate_count"] == 0


def test_record_sync_error_routes_code_sync_error_to_review_queue(monkeypatch):
    captured: list[tuple[str, str, str, str]] = []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    class _FakeRepo:
        def __init__(self, conn):  # noqa: ARG002
            pass

        def insert_review_queue(self, entity_type, entity_id, issue_type, review_note):
            captured.append((entity_type, entity_id, issue_type, review_note))

    monkeypatch.setattr(sync_script, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(sync_script, "PostgresRepository", _FakeRepo)

    args = SimpleNamespace(region_url="https://region", region_sigungu_url="https://sigungu")
    sync_script._record_sync_error(args, RuntimeError("forced-failure"))

    assert captured
    assert captured[0][0] == "code_sync_job"
    assert captured[0][2] == "code_sync_error"
    assert "forced-failure" in captured[0][3]


def test_sync_common_codes_main_runs_elections_sync(monkeypatch, tmp_path):
    rows = [
        {
            "region_code": "11-000",
            "sido_name": "서울특별시",
            "sigungu_name": "전체",
            "admin_level": "sido",
            "parent_region_code": None,
        }
    ]
    captured = {"elections_called": False}

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    class _FakeRepo:
        def __init__(self, conn):  # noqa: ARG002
            self.conn = conn

        def upsert_region(self, row):  # noqa: ARG002
            return None

    monkeypatch.setattr(sync_script, "_fetch_rows", lambda args: rows)
    monkeypatch.setattr(sync_script, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(sync_script, "PostgresRepository", _FakeRepo)
    monkeypatch.setattr(sync_script, "_load_existing_regions", lambda repo: [])

    def fake_run_elections_master_sync(*, dry_run, report_path):
        captured["elections_called"] = True
        return {
            "status": "success",
            "dry_run": dry_run,
            "report_path": report_path,
        }

    monkeypatch.setattr(sync_script, "run_elections_master_sync", fake_run_elections_master_sync)

    report_path = tmp_path / "common_codes_report.json"
    elections_report_path = tmp_path / "elections_report.json"
    args = SimpleNamespace(
        region_url="https://region",
        region_sigungu_url=None,
        party_url=None,
        election_url=None,
        dry_run=False,
        report_path=str(report_path),
        elections_report_path=str(elections_report_path),
        skip_elections_sync=False,
    )
    monkeypatch.setattr(sync_script, "parse_args", lambda: args)

    sync_script.main()

    assert captured["elections_called"] is True
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["elections_sync"]["status"] == "success"
