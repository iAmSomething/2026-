from __future__ import annotations

from src.pipeline.nesdc_pdf_adapters import NesdcPdfAdapterEngine, build_top10_pollster_template_profile


def _adapter_row(*, ntt_id: str, pollster: str, option: str = "후보A", value_raw: str = "45.0%") -> dict:
    return {
        "ntt_id": ntt_id,
        "pollster": pollster,
        "result_items": [
            {
                "question": "가상대결",
                "option": option,
                "value_raw": value_raw,
                "provenance": {"source_channel": "nesdc", "page": 1, "paragraph": 1},
            }
        ],
    }


def test_adapter_engine_prefers_exact_ntt_match() -> None:
    engine = NesdcPdfAdapterEngine(adapter_rows=[_adapter_row(ntt_id="100", pollster="A")])

    out = engine.resolve({"ntt_id": "100", "pollster": "A"})

    assert out.adapter_mode == "adapter_exact"
    assert out.fallback_applied is False
    assert out.result_items[0]["value_mid"] == 45.0


def test_adapter_engine_uses_pollster_template_fallback() -> None:
    engine = NesdcPdfAdapterEngine(adapter_rows=[_adapter_row(ntt_id="100", pollster="A")])

    out = engine.resolve({"ntt_id": "999", "pollster": "A"})

    assert out.adapter_mode == "adapter_pollster_template_fallback"
    assert out.fallback_applied is True
    assert out.matched_adapter_ntt_id == "100"


def test_adapter_engine_uses_ocr_fallback_when_text_exists() -> None:
    engine = NesdcPdfAdapterEngine(adapter_rows=[])

    out = engine.resolve({"ntt_id": "1", "pollster": "X", "ocr_text": "후보A 48.2% 후보B 41.0%"})

    assert out.adapter_mode == "adapter_ocr_fallback"
    assert [item["option"] for item in out.result_items] == ["후보A", "후보B"]


def test_adapter_engine_uses_rule_fallback_when_result_text_exists() -> None:
    engine = NesdcPdfAdapterEngine(adapter_rows=[])

    out = engine.resolve({"ntt_id": "1", "pollster": "X", "result_text": "후보A: 50% / 후보B: 40%"})

    assert out.adapter_mode == "adapter_rule_fallback"
    assert len(out.result_items) == 2


def test_top10_profile_reports_coverage_ratio() -> None:
    registry_rows = [
        {"pollster": "A"},
        {"pollster": "A"},
        {"pollster": "B"},
        {"pollster": "C"},
    ]
    adapter_rows = [_adapter_row(ntt_id="1", pollster="A"), _adapter_row(ntt_id="2", pollster="C")]

    out = build_top10_pollster_template_profile(registry_rows=registry_rows, adapter_rows=adapter_rows, top_n=3)

    assert out["top_n"] == 3
    assert out["covered_pollster_count"] == 2
    assert out["coverage_ratio"] == 0.6667
