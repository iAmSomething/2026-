from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_connection  # noqa: E402
from app.services.elections_master import build_election_slots, default_office_types_for_region  # noqa: E402
from app.services.repository import PostgresRepository  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync region x office_type election master slots.")
    parser.add_argument("--dry-run", action="store_true", help="Compute slots only. Do not write DB.")
    parser.add_argument("--report-path", default="data/elections_master_sync_report.json")
    return parser.parse_args()


def _write_report(report_path: str, payload: dict[str, Any]) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_sample_checks(slots: list[dict[str, Any]]) -> dict[str, Any]:
    by_region: dict[str, list[dict[str, Any]]] = {}
    for slot in slots:
        by_region.setdefault(slot["region_code"], []).append(slot)

    return {
        "region_32_000_slot_count": len(by_region.get("32-000", [])),
        "region_42_000_slot_count": len(by_region.get("42-000", [])),
        "region_26_710_slot_count": len(by_region.get("26-710", [])),
    }


def _count_missing_default_pairs(regions: list[dict[str, Any]], slots: list[dict[str, Any]]) -> int:
    slot_pairs = {(slot["region_code"], slot["office_type"]) for slot in slots}
    missing = 0
    for region in regions:
        region_code = str(region.get("region_code") or "")
        for office_type in default_office_types_for_region(region.get("admin_level")):
            if (region_code, office_type) not in slot_pairs:
                missing += 1
    return missing


def run_elections_master_sync(*, dry_run: bool = False, report_path: str = "data/elections_master_sync_report.json") -> dict[str, Any]:
    try:
        with get_connection() as conn:
            repo = PostgresRepository(conn)
            regions = repo.fetch_all_regions()
            latest_matchup_by_pair = repo.fetch_latest_matchup_ids_by_region_office()
            observed_byelection_pairs = repo.fetch_observed_byelection_pairs()

            slots = build_election_slots(
                regions=regions,
                latest_matchup_by_pair=latest_matchup_by_pair,
                observed_byelection_pairs=observed_byelection_pairs,
            )

            upserted = 0
            if not dry_run:
                for slot in slots:
                    repo.upsert_election_slot(slot)
                    upserted += 1

        missing_default_slot_pairs = _count_missing_default_pairs(regions, slots)
        no_poll_slots = sum(1 for slot in slots if not slot.get("has_poll_data"))
        with_poll_slots = sum(1 for slot in slots if slot.get("has_poll_data"))
        sample_checks = _build_sample_checks(slots)
        metro_sample_slot_count = max(
            int(sample_checks["region_32_000_slot_count"]),
            int(sample_checks["region_42_000_slot_count"]),
        )
        metro_sample_region_present = metro_sample_slot_count > 0

        report = {
            "status": "success",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "region_count": len(regions),
            "slot_count": len(slots),
            "upserted_slot_count": upserted,
            "with_poll_data_slot_count": with_poll_slots,
            "without_poll_data_slot_count": no_poll_slots,
            "observed_byelection_pair_count": len(observed_byelection_pairs),
            "missing_default_slot_pairs": missing_default_slot_pairs,
            "sample_checks": sample_checks,
            "acceptance_checks": {
                "default_slot_pairs_complete": missing_default_slot_pairs == 0,
                "slots_queryable_even_without_poll": no_poll_slots > 0,
                "sample_metro_region_ge_3": (not metro_sample_region_present) or metro_sample_slot_count >= 3,
                "sample_region_26_710_ge_2": sample_checks["region_26_710_slot_count"] >= 2,
            },
            "acceptance_meta": {
                "metro_sample_region_present": metro_sample_region_present,
                "metro_sample_slot_count": metro_sample_slot_count,
            },
            "sample_slots": slots[:10],
        }
        _write_report(report_path, report)
        return report
    except Exception as exc:  # noqa: BLE001
        try:
            with get_connection() as conn:
                repo = PostgresRepository(conn)
                repo.insert_review_queue(
                    entity_type="code_sync_job",
                    entity_id="elections_master_sync",
                    issue_type="code_sync_error",
                    review_note=f"{exc.__class__.__name__}: {exc}"[:2000],
                )
        except Exception:
            pass
        report = {
            "status": "failed",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
        _write_report(report_path, report)
        return report


def main() -> None:
    args = parse_args()
    report = run_elections_master_sync(dry_run=args.dry_run, report_path=args.report_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
