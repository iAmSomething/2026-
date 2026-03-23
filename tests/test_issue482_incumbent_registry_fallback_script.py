from __future__ import annotations

import json
from pathlib import Path

from scripts.run_issue482_incumbent_registry_fallback import run


def test_issue482_incumbent_registry_fallback_builds_full_regional_coverage(tmp_path: Path) -> None:
    registry_out = tmp_path / "registry.json"
    report_out = tmp_path / "report.json"
    publish_out = tmp_path / "publish.json"

    result = run(
        registry_out=registry_out,
        report_out=report_out,
        publish_out=publish_out,
        apply_db=False,
    )

    registry_payload = json.loads(registry_out.read_text(encoding="utf-8"))
    report = json.loads(report_out.read_text(encoding="utf-8"))
    publish = json.loads(publish_out.read_text(encoding="utf-8"))

    assert result["report"]["acceptance_checks"]["regional_coverage_no_missing"] is True
    assert report["acceptance_checks"]["regional_coverage_no_missing"] is True
    assert report["acceptance_checks"]["term_uncertainty_marked"] is True
    assert report["acceptance_checks"]["source_channel_separated"] is True

    records = registry_payload["records"]
    assert len(records) == 51
    assert all(row["source_channel"] == "incumbent_registry" for row in records)
    assert set(row["office_type"] for row in records) == {"광역자치단체장", "광역의회", "교육감"}
    assert report["by_office_count"]["광역자치단체장"] == 17
    assert report["by_office_count"]["광역의회"] == 17
    assert report["by_office_count"]["교육감"] == 17

    assert publish["applied"] is False
    assert publish["upserted_count"] == 0
