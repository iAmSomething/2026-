from __future__ import annotations

from collections import Counter

from scripts.generate_collector_party_inference_v2_batch50 import (
    _extract_party_mentions,
    _is_candidate_name_like,
    infer_party_for_candidate,
)


class _FakeProvider:
    def __init__(self):
        self.rows = {
            ("서울특별시", "강남구", False, False, "오세훈"): [
                {"name": "오세훈", "jdName": "국민의힘", "_sg_typecode": "4"}
            ],
            ("서울특별시", "강남구", True, True, "정원오"): [
                {"name": "정원오", "jdName": "더불어민주당", "_sg_typecode": "4"},
                {"name": "정원오", "jdName": "더불어민주당", "_sg_typecode": "3"},
            ],
        }

    def find_matches(
        self,
        *,
        candidate_name: str,
        sd_name: str | None,
        sgg_name: str | None,
        office_type: str | None,
        include_sd_fallback: bool,
        include_global: bool,
    ):
        _ = office_type
        return self.rows.get((sd_name, sgg_name, include_sd_fallback, include_global, candidate_name), [])


def test_candidate_name_like_filters_noise_tokens() -> None:
    assert _is_candidate_name_like("오세훈") is True
    assert _is_candidate_name_like("서울시장") is False
    assert _is_candidate_name_like("더불어민주당") is False


def test_extract_party_mentions_from_context() -> None:
    text = "국민의힘 오세훈 후보가 앞섰다."
    mentions = _extract_party_mentions(text, "오세훈")
    parties = [row[0] for row in mentions]
    assert "국민의힘" in parties


def test_infer_party_prefers_data_go_region_source() -> None:
    provider = _FakeProvider()
    out = infer_party_for_candidate(
        candidate_name="오세훈",
        article_text="더불어민주당 오세훈 후보라는 오기 문구",
        region_code="11-680",
        office_type="기초자치단체장",
        provider=provider,  # type: ignore[arg-type]
        latest_registry=None,
    )

    assert out.party_inferred == "국민의힘"
    assert out.party_inference_source == "data_go_candidate_api_region"
    assert out.party_inference_confidence >= 0.84
    assert out.confidence_tier in {"high", "mid"}


def test_infer_party_uses_context_registry_fallback() -> None:
    provider = _FakeProvider()
    out = infer_party_for_candidate(
        candidate_name="김경수",
        article_text="단순 이름만 노출",
        region_code="48-000",
        office_type="광역자치단체장",
        provider=provider,  # type: ignore[arg-type]
        latest_registry={"김경수": Counter({"더불어민주당": 3})},
    )

    assert out.party_inferred == "더불어민주당"
    assert out.party_inference_source == "context_registry_v2"
    assert out.party_inference_confidence >= 0.75


def test_infer_party_blocks_conflicting_signals() -> None:
    provider = _FakeProvider()
    out = infer_party_for_candidate(
        candidate_name="오세훈",
        article_text="민주 오세훈 후보와 국힘 오세훈 후보 언급",
        region_code="26-000",
        office_type="광역자치단체장",
        provider=provider,  # type: ignore[arg-type]
        latest_registry=None,
    )

    assert out.party_inferred is None
    assert out.blocked_reason == "conflicting_party_signals"
