from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

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
        raise SystemExit("[FAIL] DATA_GO_KR_KEY is empty. Set env and retry.")

    main_service = _build_service(args.region_url, args)
    main_items = main_service.fetch_items()

    sigungu_items: list[dict] = []
    if args.region_sigungu_url:
        sigungu_service = _build_service(args.region_sigungu_url, args)
        sigungu_items = sigungu_service.fetch_items()

    return build_region_rows([*main_items, *sigungu_items])


def _write_report(report_path: str, payload: dict) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    rows = _fetch_rows(args)

    if not rows:
        raise SystemExit("[FAIL] No region rows parsed from CommonCodeService response.")

    upserted = 0
    if not args.dry_run:
        with get_connection() as conn:
            repo = PostgresRepository(conn)
            for row in rows:
                repo.upsert_region(row)
                upserted += 1

    report = {
        "region_url": args.region_url,
        "region_sigungu_url": args.region_sigungu_url,
        "party_url": args.party_url,
        "election_url": args.election_url,
        "dry_run": args.dry_run,
        "parsed_region_count": len(rows),
        "upserted_region_count": upserted,
        "sample": rows[:5],
    }
    _write_report(args.report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
