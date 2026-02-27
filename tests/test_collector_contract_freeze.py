import pytest

from src.pipeline.collector import PollCollector
from src.pipeline.contracts import Article, build_matchup_id, new_review_queue_item, stable_id
from src.pipeline.standards import ISSUE_TAXONOMY, OFFICE_TYPE_STANDARD


def _article(text: str, title: str = "샘플 기사"):
    return Article(
        id=stable_id("art", title, text),
        url="https://example.com/a",
        title=title,
        publisher="샘플뉴스",
        published_at="2026-02-18T00:00:00+09:00",
        snippet=text[:100],
        collected_at="2026-02-18T00:00:00+00:00",
        raw_hash=stable_id("hash", text),
        raw_text=text,
    )


def test_office_type_is_korean_standard_value():
    collector = PollCollector(election_id="20260603")
    article = _article("서울시장 여론조사 KBS 발표 정원오 44% vs 오세훈 31%")
    observations, options, errors = collector.extract(article)

    assert not errors
    assert observations
    assert options
    assert observations[0].office_type in OFFICE_TYPE_STANDARD
    assert observations[0].office_type == "광역자치단체장"
    assert observations[0].region_code == "11-000"
    assert observations[0].matchup_id == build_matchup_id("20260603", "광역자치단체장", "11-000")


def test_unmapped_region_is_mapping_error_without_temp_code():
    collector = PollCollector(election_id="20260603")
    article = _article("알수없는지역시장 여론조사 정원오 44% vs 오세훈 31%")
    observations, options, errors = collector.extract(article)

    assert not observations
    assert not options
    assert errors
    assert errors[0].issue_type == "mapping_error"
    assert errors[0].error_code == "REGION_OFFICE_NOT_MAPPED"


def test_sigungu_mapping_expansion_for_local_office():
    collector = PollCollector(election_id="20260603")
    article = _article("서울 강남구청장 여론조사 정원오 44% vs 오세훈 31%")
    observations, options, errors = collector.extract(article)

    assert not errors
    assert observations
    assert observations[0].region_code == "11-680"
    assert observations[0].office_type == "기초자치단체장"
    assert observations[0].matchup_id == build_matchup_id("20260603", "기초자치단체장", "11-680")
    assert len(options) == 2


def test_dojisa_variant_mapping():
    collector = PollCollector(election_id="20260603")
    article = _article("제주도지사 여론조사 고희범 37% vs 허향진 34%")
    observations, options, errors = collector.extract(article)

    assert not errors
    assert observations
    assert observations[0].region_code == "50-000"
    assert observations[0].office_type == "광역자치단체장"
    assert observations[0].matchup_id == build_matchup_id("20260603", "광역자치단체장", "50-000")
    assert len(options) == 2


def test_review_queue_issue_type_must_be_fixed_taxonomy():
    assert "discover_error" in ISSUE_TAXONOMY
    assert "ingestion_error" in ISSUE_TAXONOMY
    assert "metadata_cross_contamination" in ISSUE_TAXONOMY
    with pytest.raises(ValueError):
        new_review_queue_item(
            entity_type="article",
            entity_id="a",
            issue_type="not_allowed",
            stage="extract",
            error_code="X",
            error_message="invalid",
        )
