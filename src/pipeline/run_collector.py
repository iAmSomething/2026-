from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .collector import PollCollector
from .contracts import INPUT_CONTRACT_SCHEMAS, REVIEW_QUEUE_SCHEMA


def _load_lines(path: str | None) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _dump_json(payload: dict[str, Any], output_path: str | None) -> None:
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(raw + "\n", encoding="utf-8")
        return
    print(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poll article collector (discover/fetch/classify/extract)")
    parser.add_argument("--seed", action="append", default=[], help="Seed URL (repeatable)")
    parser.add_argument("--seed-file", help="Path to file with seed URLs (one per line)")
    parser.add_argument("--rss", action="append", default=[], help="RSS URL (repeatable)")
    parser.add_argument("--rss-file", help="Path to file with RSS URLs (one per line)")
    parser.add_argument("--election-id", default="2026_local", help="Election id used for matchup_id")
    parser.add_argument("--output", help="Write output JSON to this file")
    parser.add_argument(
        "--relative-date-policy",
        default=None,
        choices=["strict_fail", "allow_estimated_timestamp"],
        help="Relative date inference policy when article.published_at is missing",
    )
    parser.add_argument("--print-contracts", action="store_true", help="Print input/error contract schemas")
    parser.add_argument("--print-query-templates", action="store_true", help="Print discovery query templates")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    seeds = [*args.seed, *_load_lines(args.seed_file)]
    rss_feeds = [*args.rss, *_load_lines(args.rss_file)]

    collector = PollCollector(election_id=args.election_id, relative_date_policy=args.relative_date_policy)
    result = collector.run(seeds=seeds, rss_feeds=rss_feeds)
    payload: dict[str, Any] = result.to_dict()

    if args.print_contracts:
        payload["contracts"] = {
            "input": INPUT_CONTRACT_SCHEMAS,
            "error": {"review_queue": REVIEW_QUEUE_SCHEMA},
        }
    if args.print_query_templates:
        payload["query_templates"] = collector.discovery_query_templates()

    _dump_json(payload, args.output)


if __name__ == "__main__":
    main()
