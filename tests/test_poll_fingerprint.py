from app.services.errors import DuplicateConflictError
from app.services.fingerprint import build_poll_fingerprint, merge_observation_by_priority


def test_poll_fingerprint_is_stable_for_normalized_values():
    left = {
        "pollster": " KBS ",
        "sponsor": "서울일보",
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "region_code": "11-000",
        "sample_size": 1000,
        "method": "전화면접",
    }
    right = {
        "pollster": "kbs",
        "sponsor": "서울일보",
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "region_code": "11-000",
        "sample_size": "1000",
        "method": "  전화면접  ",
    }
    assert build_poll_fingerprint(left) == build_poll_fingerprint(right)


def test_merge_prefers_nesdc_metadata_and_keeps_article_context():
    existing = {
        "observation_key": "obs-article",
        "article_id": 101,
        "survey_name": "기사 제목 기반 조사",
        "pollster": "미상",
        "sponsor": None,
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "sample_size": 1000,
        "response_rate": None,
        "margin_of_error": 3.1,
        "method": None,
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "matchup_id": "20260603|광역자치단체장|11-000",
        "poll_fingerprint": "fp1",
        "source_channel": "article",
        "verified": False,
        "source_grade": "C",
        "ingestion_run_id": 1,
    }
    incoming = {
        "observation_key": "obs-nesdc",
        "article_id": 202,
        "survey_name": "NESDC 원문",
        "pollster": "KBS",
        "sponsor": "중앙선거여론조사심의위",
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "sample_size": 1000,
        "response_rate": 11.2,
        "margin_of_error": 3.1,
        "method": "전화면접",
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "matchup_id": "20260603|광역자치단체장|11-000",
        "poll_fingerprint": "fp1",
        "source_channel": "nesdc",
        "verified": True,
        "source_grade": "A",
        "ingestion_run_id": 2,
    }
    merged = merge_observation_by_priority(existing=existing, incoming=incoming)

    assert merged["observation_key"] == "obs-article"
    assert merged["source_channel"] == "nesdc"
    assert merged["pollster"] == "KBS"
    assert merged["method"] == "전화면접"
    assert merged["survey_name"] == "기사 제목 기반 조사"
    assert merged["article_id"] == 101
    assert merged["verified"] is True


def test_merge_raises_duplicate_conflict_on_core_mismatch():
    existing = {
        "observation_key": "obs-1",
        "source_channel": "article",
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "sample_size": 1000,
    }
    incoming = {
        "observation_key": "obs-2",
        "source_channel": "nesdc",
        "region_code": "11-000",
        "office_type": "광역자치단체장",
        "survey_start_date": "2026-02-10",
        "survey_end_date": "2026-02-12",
        "sample_size": 1200,
    }
    try:
        merge_observation_by_priority(existing=existing, incoming=incoming)
        raise AssertionError("expected DuplicateConflictError")
    except DuplicateConflictError as exc:
        assert "DUPLICATE_CONFLICT" in str(exc)

