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
