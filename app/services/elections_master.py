from __future__ import annotations

from typing import Any

METRO_OFFICE_TYPES: tuple[str, ...] = ("광역자치단체장", "광역의회", "교육감")
LOCAL_OFFICE_TYPES: tuple[str, ...] = ("기초자치단체장", "기초의회")


def default_office_types_for_region(admin_level: str | None) -> tuple[str, ...]:
    if (admin_level or "").strip().lower() == "sigungu":
        return LOCAL_OFFICE_TYPES
    return METRO_OFFICE_TYPES


def build_slot_title(region: dict[str, Any], office_type: str) -> str:
    sido_name = str(region.get("sido_name") or "").strip()
    sigungu_name = str(region.get("sigungu_name") or "").strip()
    admin_level = str(region.get("admin_level") or "").strip().lower()
    if admin_level == "sigungu" and sigungu_name and sigungu_name != "전체":
        return f"{sido_name} {sigungu_name} {office_type}".strip()
    return f"{sido_name} {office_type}".strip() or office_type


def build_slot_matchup_id(region_code: str, office_type: str) -> str:
    return f"master|{office_type}|{region_code}"


def build_election_slots(
    *,
    regions: list[dict[str, Any]],
    latest_matchup_by_pair: dict[tuple[str, str], str],
    observed_byelection_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for region in regions:
        region_code = str(region.get("region_code") or "").strip()
        if not region_code:
            continue

        office_types = list(default_office_types_for_region(region.get("admin_level")))
        for observed_region_code, observed_office_type in sorted(observed_byelection_pairs):
            if observed_region_code == region_code and observed_office_type not in office_types:
                office_types.append(observed_office_type)

        for office_type in office_types:
            latest_matchup_id = latest_matchup_by_pair.get((region_code, office_type))
            slots.append(
                {
                    "region_code": region_code,
                    "office_type": office_type,
                    "slot_matchup_id": build_slot_matchup_id(region_code, office_type),
                    "title": build_slot_title(region, office_type),
                    "source": "code_master",
                    "has_poll_data": bool(latest_matchup_id),
                    "latest_matchup_id": latest_matchup_id,
                    "is_active": True,
                }
            )
    return slots
