from __future__ import annotations

import pytest

from scripts import generate_nesdc_pdf_adapter_v2_5pollsters as adapter


def test_parse_list_page_builds_canonical_detail_url() -> None:
    html = """
    <a href="/portal/bbs/B0000005/view.do?nttId=17458&menuNo=200467&searchWrd=(주)엠브레인퍼블릭&pageIndex=1" class="row tr">
      <span class="col"><i class="tit"></i>15395</span>
      <span class="col"><i class="tit"></i>(주)엠브레인퍼블릭</span>
      <span class="col"><i class="tit"></i>목포MBC</span>
      <span class="col"><i class="tit"></i>무선전화면접</span>
      <span class="col"><i class="tit"></i>무선전화번호 휴대전화 가상번호</span>
      <span class="col"><i class="tit"></i>전국 광역단체장선거</span>
      <span class="col"><i class="tit"></i>2026-02-17</span>
      <span class="col"><i class="tit"></i>전국</span>
    </a>
    """
    rows = adapter._parse_list_page(html)
    assert len(rows) == 1
    assert rows[0]["ntt_id"] == "17458"
    assert rows[0]["detail_url"].endswith("view.do?menuNo=200467&nttId=17458")


def test_generate_adapter_v2_5pollsters_fails_when_pollster_floor_not_met(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "TARGET_POLLSTERS", ("A", "B", "C", "D", "E"))
    monkeypatch.setattr(adapter, "MIN_PER_POLLSTER", 2)

    def fake_collect(pollster: str, min_count: int = 40) -> list[dict[str, str]]:
        if pollster == "A":
            return [
                {"detail_url": "https://x/1", "pollster": "A"},
                {"detail_url": "https://x/2", "pollster": "A"},
            ]
        if pollster == "B":
            return [
                {"detail_url": "https://x/3", "pollster": "B"},
                {"detail_url": "https://x/4", "pollster": "B"},
            ]
        if pollster == "C":
            return [
                {"detail_url": "https://x/5", "pollster": "C"},
                {"detail_url": "https://x/6", "pollster": "C"},
            ]
        if pollster == "D":
            return [
                {"detail_url": "https://x/7", "pollster": "D"},
                {"detail_url": "https://x/8", "pollster": "D"},
            ]
        return [{"detail_url": "https://x/9", "pollster": "E"}]

    def fake_parse(row: dict[str, str]) -> dict:
        return {
            **row,
            "_html_rows": [{"ths": [], "html": "<th>결과분석 자료</th><th>최초 공표·보도 지정일시</th>"}],
            "_gold_result_items": [("가상후보", "45.0%")],
            "result_items": [{"option": "가상후보", "value_raw": "45.0%"}],
            "legal_meta": {"method": "무선전화면접"},
        }

    monkeypatch.setattr(adapter, "_collect_pollster_rows", fake_collect)
    monkeypatch.setattr(adapter, "_parse_detail", fake_parse)

    with pytest.raises(RuntimeError, match="insufficient samples per pollster"):
        adapter.generate_adapter_v2_5pollsters()


def test_evaluate_tracks_result_mismatch_failures() -> None:
    rec = {
        "_html_rows": [{"ths": ["조사일시"], "tds": ["2026-01-01"], "html": "<tr><th>조사일시</th><td>2026-01-01</td></tr>"}],
        "legal_meta": {
            "survey_datetime": "2026-01-01",
            "survey_population": None,
            "sample_size": None,
            "response_rate": None,
            "margin_of_error": None,
            "method": "무선전화면접",
        },
        "result_items": [{"option": "A", "value_raw": "40%"}],
        "_gold_result_items": [("B", "41%")],
        "pollster": "A",
    }
    out = adapter._evaluate([rec])
    tops = {row["type"]: row["count"] for row in out["failure_types_top5"]}
    assert tops["RESULT_OPTION_VALUE_MISMATCH_FP"] == 1
    assert tops["RESULT_OPTION_VALUE_MISMATCH_FN"] == 1
