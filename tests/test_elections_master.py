from __future__ import annotations

from app.services.elections_master import (
    build_election_slots,
    default_office_types_for_region,
)


def test_default_office_types_for_region_by_admin_level() -> None:
    assert default_office_types_for_region("sido") == ("광역자치단체장", "광역의회", "교육감")
    assert default_office_types_for_region("sigungu") == ("기초자치단체장", "기초의회")


def test_build_election_slots_adds_default_and_byelection_slots() -> None:
    regions = [
        {
            "region_code": "32-000",
            "sido_name": "강원특별자치도",
            "sigungu_name": "전체",
            "admin_level": "sido",
        },
        {
            "region_code": "26-710",
            "sido_name": "부산광역시",
            "sigungu_name": "부산진구",
            "admin_level": "sigungu",
        },
    ]
    latest_map = {
        ("32-000", "광역자치단체장"): "20260603|광역자치단체장|32-000",
    }
    observed_byelection_pairs = {("26-710", "기초자치단체장 재보궐")}

    slots = build_election_slots(
        regions=regions,
        latest_matchup_by_pair=latest_map,
        observed_byelection_pairs=observed_byelection_pairs,
    )
    pairs = {(row["region_code"], row["office_type"]) for row in slots}

    assert ("32-000", "광역자치단체장") in pairs
    assert ("32-000", "광역의회") in pairs
    assert ("32-000", "교육감") in pairs
    assert ("26-710", "기초자치단체장") in pairs
    assert ("26-710", "기초의회") in pairs
    assert ("26-710", "기초자치단체장 재보궐") in pairs

    metro_row = next(row for row in slots if row["region_code"] == "32-000" and row["office_type"] == "광역자치단체장")
    assert metro_row["has_poll_data"] is True
    assert metro_row["latest_matchup_id"] == "20260603|광역자치단체장|32-000"
