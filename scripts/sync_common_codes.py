from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_connection
from app.services.data_go_common_codes import (  # noqa: E402
    DataGoCommonCodeConfig,
    DataGoCommonCodeService,
    build_region_rows,
)
from app.services.repository import PostgresRepository  # noqa: E402
from scripts.sync_elections_master import run_elections_master_sync  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync CommonCodeService regions into regions table.")
    parser.add_argument("--region-url", required=True, help="Data.go CommonCodeService region endpoint URL")
    parser.add_argument(
        "--region-sigungu-url",
        default=None,
        help="Optional secondary endpoint URL for 시군구 list (if region-url returns only 시도).",
    )
    parser.add_argument("--party-url", default=None, help="Reserved for future party code sync")
    parser.add_argument("--election-url", default=None, help="Reserved for future election code sync")
    parser.add_argument("--timeout-sec", type=float, default=6.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--num-of-rows", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse only. Do not write DB.")
    parser.add_argument("--report-path", default="data/common_codes_sync_report.json")
    parser.add_argument("--elections-report-path", default="data/elections_master_sync_report.json")
    parser.add_argument(
        "--skip-elections-sync",
        action="store_true",
        help="Do not run elections master sync after region code sync.",
    )
    return parser.parse_args()


def _build_service(endpoint_url: str, args: argparse.Namespace) -> DataGoCommonCodeService:
    return DataGoCommonCodeService(
        DataGoCommonCodeConfig(
            endpoint_url=endpoint_url,
            service_key=os.getenv("DATA_GO_KR_KEY"),
            timeout_sec=args.timeout_sec,
            max_retries=args.max_retries,
            num_of_rows=args.num_of_rows,
        )
    )


def _fetch_rows(args: argparse.Namespace) -> list[dict]:
    service_key = os.getenv("DATA_GO_KR_KEY", "").strip()
    if not service_key:
        raise RuntimeError("DATA_GO_KR_KEY is empty. Set env and retry.")

    main_service = _build_service(args.region_url, args)
    main_items = main_service.fetch_items()

    sigungu_items: list[dict] = []
    if args.region_sigungu_url:
        sigungu_service = _build_service(args.region_sigungu_url, args)
        sigungu_items = sigungu_service.fetch_items()

    return build_region_rows([*main_items, *sigungu_items])


def _load_existing_regions(repo: PostgresRepository) -> list[dict[str, Any]]:
    with repo.conn.cursor() as cur:
        cur.execute(
            """
            SELECT region_code, sido_name, sigungu_name, admin_level, parent_region_code
            FROM regions
            """
        )
        rows = cur.fetchall() or []
    return [dict(row) for row in rows]


def _compute_region_diff(existing_rows: list[dict[str, Any]], fetched_rows: list[dict[str, Any]]) -> dict[str, Any]:
    existing_map = {str(row["region_code"]): row for row in existing_rows}
    fetched_map = {str(row["region_code"]): row for row in fetched_rows}

    added: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    delete_candidates: list[str] = []

    for code, row in fetched_map.items():
        prev = existing_map.get(code)
        if prev is None:
            added.append(code)
            continue
        if not _region_rows_equal(prev, row):
            updated.append(code)
        else:
            unchanged.append(code)

    for code in existing_map:
        if code not in fetched_map:
            delete_candidates.append(code)

    return {
        "existing_total": len(existing_map),
        "fetched_total": len(fetched_map),
        "added_count": len(added),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "delete_candidate_count": len(delete_candidates),
        "added_sample": sorted(added)[:20],
        "updated_sample": sorted(updated)[:20],
        "delete_candidate_sample": sorted(delete_candidates)[:20],
    }


def _region_rows_equal(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    for field in ("sido_name", "sigungu_name", "admin_level", "parent_region_code"):
        if (existing.get(field) or None) != (incoming.get(field) or None):
            return False
    return True


def _record_sync_error(args: argparse.Namespace, error: Exception) -> None:
    try:
        with get_connection() as conn:
            repo = PostgresRepository(conn)
            repo.insert_review_queue(
                entity_type="code_sync_job",
                entity_id="common_codes_region_sync",
                issue_type="code_sync_error",
                review_note=(
                    f"{error.__class__.__name__}: {error} "
                    f"(region_url={args.region_url}, region_sigungu_url={args.region_sigungu_url})"
                )[:2000],
            )
    except Exception:
        pass


def _write_report(report_path: str, payload: dict) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    try:
        rows = _fetch_rows(args)
        if not rows:
            raise RuntimeError("No region rows parsed from CommonCodeService response.")

        upserted = 0
        diff = {
            "existing_total": 0,
            "fetched_total": len(rows),
            "added_count": len(rows),
            "updated_count": 0,
            "unchanged_count": 0,
            "delete_candidate_count": 0,
            "added_sample": [row["region_code"] for row in rows[:20]],
            "updated_sample": [],
            "delete_candidate_sample": [],
        }
        if args.dry_run:
            try:
                with get_connection() as conn:
                    repo = PostgresRepository(conn)
                    existing_rows = _load_existing_regions(repo)
                    diff = _compute_region_diff(existing_rows=existing_rows, fetched_rows=rows)
            except Exception as exc:
                diff["warning"] = f"dry_run without DB diff: {exc.__class__.__name__}: {exc}"
        else:
            with get_connection() as conn:
                repo = PostgresRepository(conn)
                existing_rows = _load_existing_regions(repo)
                diff = _compute_region_diff(existing_rows=existing_rows, fetched_rows=rows)
                existing_map = {str(row["region_code"]): row for row in existing_rows}
                changed_codes = {
                    row["region_code"]
                    for row in rows
                    if str(row["region_code"]) not in existing_map
                    or not _region_rows_equal(existing_map[str(row["region_code"])], row)
                }
                for row in rows:
                    if row["region_code"] not in changed_codes:
                        continue
                    repo.upsert_region(row)
                    upserted += 1

        elections_sync: dict[str, Any] | None = None
        if not args.skip_elections_sync:
            elections_sync = run_elections_master_sync(
                dry_run=args.dry_run,
                report_path=args.elections_report_path,
            )

        report = {
            "status": "success",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "region_url": args.region_url,
            "region_sigungu_url": args.region_sigungu_url,
            "party_url": args.party_url,
            "election_url": args.election_url,
            "dry_run": args.dry_run,
            "parsed_region_count": len(rows),
            "upserted_region_count": upserted,
            "skip_elections_sync": args.skip_elections_sync,
            "elections_sync_report_path": args.elections_report_path,
            "elections_sync": elections_sync,
            "diff": diff,
            "sample": rows[:5],
        }
        _write_report(args.report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as exc:
        _record_sync_error(args, exc)
        report = {
            "status": "failed",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "region_url": args.region_url,
            "region_sigungu_url": args.region_sigungu_url,
            "party_url": args.party_url,
            "election_url": args.election_url,
            "dry_run": args.dry_run,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
        _write_report(args.report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(f"[FAIL] {exc}") from exc


if __name__ == "__main__":
    main()
