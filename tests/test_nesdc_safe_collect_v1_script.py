from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.generate_nesdc_safe_collect_v1 import generate_nesdc_safe_collect_v1

KST = ZoneInfo("Asia/Seoul")


def _registry_row(
    *,
    ntt_id: str,
    pollster: str,
    eligible: bool,
) -> dict:
    return {
        "ntt_id": ntt_id,
        "detail_url": f"https://nesdc.test/{ntt_id}",
        "pollster": pollster,
        "registered_at": "2026-02-20 09:00",
        "first_publish_at_kst": "2026-02-20 09:30",
        "survey_datetime_text": "2026-02-19",
        "survey_population": "전국 만 18세 이상",
        "sample_size": 1000,
        "response_rate": 12.3,
        "margin_of_error_text": "95% 신뢰수준 ±3.1%p",
        "method": "전화면접",
        "auto_collect_eligible_48h": eligible,
    }


def _adapter_row(*, ntt_id: str) -> dict:
    return {
        "ntt_id": ntt_id,
        "result_items": [
            {
                "question": "가상대결",
                "option": "후보A",
                "value_raw": "45.0%",
                "provenance": {"source_channel": "nesdc", "page": 1, "paragraph": 1},
            }
        ],
    }


def test_safe_collect_applies_48h_and_routes_fallback(tmp_path: Path) -> None:
    registry = {
        "records": [
            _registry_row(ntt_id="1", pollster="A", eligible=True),
            _registry_row(ntt_id="2", pollster="B", eligible=True),
            _registry_row(ntt_id="3", pollster="C", eligible=True),
            _registry_row(ntt_id="4", pollster="D", eligible=True),
            _registry_row(ntt_id="5", pollster="E", eligible=True),
            _registry_row(ntt_id="6", pollster="F", eligible=True),
            _registry_row(ntt_id="7", pollster="X", eligible=False),
        ]
    }
    adapter = {
        "records": [
            _adapter_row(ntt_id="1"),
            _adapter_row(ntt_id="2"),
            _adapter_row(ntt_id="3"),
            _adapter_row(ntt_id="4"),
            _adapter_row(ntt_id="5"),
        ]
    }

    reg_path = tmp_path / "registry.json"
    adp_path = tmp_path / "adapter.json"
    reg_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    adp_path.write_text(json.dumps(adapter, ensure_ascii=False), encoding="utf-8")

    out = generate_nesdc_safe_collect_v1(
        registry_path=str(reg_path),
        adapter_path=str(adp_path),
        as_of_kst=datetime(2026, 2, 23, 12, 0, tzinfo=KST),
    )

    report = out["report"]
    assert report["counts"]["eligible_48h_total"] == 6
    assert report["counts"]["collected_success_count"] == 5
    assert report["counts"]["fallback_count"] == 1
    assert report["acceptance_checks"]["fallback_review_queue_synced"] is True
    assert len(out["review_queue_candidates"]) == 1


def test_safe_collect_stores_raw_and_normalized_values(tmp_path: Path) -> None:
    registry = {"records": [_registry_row(ntt_id="1", pollster="A", eligible=True)]}
    adapter = {"records": [_adapter_row(ntt_id="1")]}

    reg_path = tmp_path / "registry.json"
    adp_path = tmp_path / "adapter.json"
    reg_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    adp_path.write_text(json.dumps(adapter, ensure_ascii=False), encoding="utf-8")

    out = generate_nesdc_safe_collect_v1(
        registry_path=str(reg_path),
        adapter_path=str(adp_path),
        as_of_kst=datetime(2026, 2, 23, 12, 0, tzinfo=KST),
    )

    opt = out["data"]["records"][0]["result_options"][0]
    assert opt["value_raw"] == "45.0%"
    assert opt["value_mid"] == 45.0
    assert opt["value_min"] == 45.0
    assert opt["value_max"] == 45.0


def test_safe_collect_pollster_coverage_regression_ge_5(tmp_path: Path) -> None:
    registry = {
        "records": [
            _registry_row(ntt_id="1", pollster="A", eligible=True),
            _registry_row(ntt_id="2", pollster="B", eligible=True),
            _registry_row(ntt_id="3", pollster="C", eligible=True),
            _registry_row(ntt_id="4", pollster="D", eligible=True),
            _registry_row(ntt_id="5", pollster="E", eligible=True),
        ]
    }
    adapter = {
        "records": [
            _adapter_row(ntt_id="1"),
            _adapter_row(ntt_id="2"),
            _adapter_row(ntt_id="3"),
            _adapter_row(ntt_id="4"),
            _adapter_row(ntt_id="5"),
        ]
    }

    reg_path = tmp_path / "registry.json"
    adp_path = tmp_path / "adapter.json"
    reg_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    adp_path.write_text(json.dumps(adapter, ensure_ascii=False), encoding="utf-8")

    out = generate_nesdc_safe_collect_v1(
        registry_path=str(reg_path),
        adapter_path=str(adp_path),
        as_of_kst=datetime(2026, 2, 23, 12, 0, tzinfo=KST),
    )

    assert out["report"]["acceptance_checks"]["pollster_coverage_ge_5"] is True
