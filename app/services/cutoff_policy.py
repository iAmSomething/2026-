from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

KST = timezone(timedelta(hours=9))
ARTICLE_PUBLISHED_AT_CUTOFF_KST = datetime(2025, 12, 1, 0, 0, 0, tzinfo=KST)
ARTICLE_PUBLISHED_AT_CUTOFF_ISO = ARTICLE_PUBLISHED_AT_CUTOFF_KST.isoformat(timespec="seconds")


def parse_datetime_like(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def published_at_cutoff_reason(published_at: Any) -> str:
    parsed = parse_datetime_like(published_at)
    if parsed is None:
        return "PASS"
    if parsed < ARTICLE_PUBLISHED_AT_CUTOFF_KST:
        return "PUBLISHED_AT_BEFORE_CUTOFF"
    return "PASS"


def is_article_published_at_allowed(published_at: Any) -> bool:
    return published_at_cutoff_reason(published_at) == "PASS"


def has_article_source(source_channel: str | None, source_channels: list[str] | None) -> bool:
    channels = list(source_channels or [])
    if not channels and source_channel:
        channels.append(source_channel)
    if not channels:
        return True
    return "article" in {x.strip().lower() for x in channels if x}
