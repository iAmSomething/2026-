from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

ROLE_LABELS = {"role/uiux", "role/collector", "role/develop", "role/qa"}


def parse_bool_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def select_reopen_candidates(
    issues: list[dict[str, Any]],
    *,
    allow_reopen_done: bool,
    lookback_days: int,
    now: datetime | None = None,
) -> list[int]:
    if not allow_reopen_done:
        return []

    now_utc = now or datetime.now(timezone.utc)
    lookback = max(0, int(lookback_days))
    cutoff = now_utc - timedelta(days=lookback)

    candidates: list[int] = []
    for issue in issues:
        if issue.get("state") != "CLOSED":
            continue

        labels = {label.get("name") for label in issue.get("labels", []) if isinstance(label, dict)}
        if "status/done" not in labels:
            continue
        if labels.isdisjoint(ROLE_LABELS):
            continue

        updated_at = parse_iso_datetime(issue.get("updatedAt"))
        if updated_at is not None and updated_at < cutoff:
            continue

        number = issue.get("number")
        if isinstance(number, int):
            candidates.append(number)

    return sorted(candidates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select PM cycle reopen candidates")
    parser.add_argument("--allow-reopen-done", default="false")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--now", default=None, help="ISO8601 current time override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issues = json.load(sys.stdin)
    now = parse_iso_datetime(args.now)
    candidates = select_reopen_candidates(
        issues,
        allow_reopen_done=parse_bool_flag(args.allow_reopen_done, default=False),
        lookback_days=args.lookback_days,
        now=now,
    )
    for number in candidates:
        print(number)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
