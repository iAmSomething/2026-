from datetime import datetime, timezone

from app.services.cutoff_policy import (
    ARTICLE_PUBLISHED_AT_CUTOFF_KST,
    has_article_source,
    is_article_published_at_allowed,
    parse_datetime_like,
    published_at_cutoff_reason,
)


def test_parse_datetime_like_supports_iso_and_rfc2822():
    iso = parse_datetime_like("2025-12-01T00:00:00+09:00")
    rfc = parse_datetime_like("Mon, 01 Dec 2025 00:00:00 +0900")

    assert iso == ARTICLE_PUBLISHED_AT_CUTOFF_KST
    assert rfc == ARTICLE_PUBLISHED_AT_CUTOFF_KST


def test_parse_datetime_like_normalizes_to_kst():
    parsed = parse_datetime_like(datetime(2025, 11, 30, 15, 0, 0, tzinfo=timezone.utc))
    assert parsed == ARTICLE_PUBLISHED_AT_CUTOFF_KST


def test_cutoff_reason_and_allowance():
    assert published_at_cutoff_reason(None) == "PASS"
    assert published_at_cutoff_reason("2025-11-30T23:59:59+09:00") == "PUBLISHED_AT_BEFORE_CUTOFF"
    assert published_at_cutoff_reason("2025-12-01T00:00:00+09:00") == "PASS"
    assert is_article_published_at_allowed("2025-12-01T00:00:00+09:00") is True


def test_has_article_source_defaults_to_true_without_source_fields():
    assert has_article_source(None, None) is True
    assert has_article_source("article", None) is True
    assert has_article_source("nesdc", ["nesdc"]) is False
