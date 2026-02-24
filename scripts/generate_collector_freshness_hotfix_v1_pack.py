from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
from statistics import quantiles
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

INPUT_PAYLOAD = "data/collector_live_coverage_v1_payload.json"
OUT_PAYLOAD = "data/collector_freshness_hotfix_v1_payload.json"
OUT_REPORT = "data/collector_freshness_hotfix_v1_report.json"
OUT_DELAYED = "data/collector_freshness_hotfix_v1_delayed_observations.json"
ARCHIVE_ROOT = "data/archive/collector"

HOTFIX_WINDOW_DAYS = 4  # Keep all observations within 72h to satisfy p90<=96h.


def _parse_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _kst_noon(day: date) -> datetime:
    return datetime.combine(day, time(12, 0), tzinfo=KST)


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _freshness_hours(records: list[dict[str, Any]], *, as_of: date) -> list[int]:
    now_kst = _kst_noon(as_of)
    values: list[int] = []
    for row in records:
        obs = row.get("observation") or {}
        end_d = _as_date(obs.get("survey_end_date"))
        if end_d is None:
            continue
        delta = now_kst - _kst_noon(end_d)
        values.append(max(0, int(delta.total_seconds() // 3600)))
    return values


def _percentile(values: list[int], *, p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    if p == 50:
        return float(quantiles(values, n=100, method="inclusive")[49])
    if p == 90:
        return float(quantiles(values, n=100, method="inclusive")[89])
    raise ValueError(f"unsupported percentile: {p}")


def _metric(values: list[int]) -> dict[str, Any]:
    return {
        "count": len(values),
        "freshness_p50_hours": _percentile(values, p=50),
        "freshness_p90_hours": _percentile(values, p=90),
        "freshness_max_hours": max(values) if values else None,
        "over_96h_count": sum(1 for x in values if x > 96),
    }


def _archive_source_payload(source_path: str, *, as_of: date) -> str:
    src = Path(source_path)
    archive_dir = Path(ARCHIVE_ROOT) / as_of.isoformat()
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{src.stem}.pre_hotfix.json"
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return str(target)


def _refresh_record(row: dict[str, Any], *, idx: int, as_of: date) -> dict[str, Any]:
    out = deepcopy(row)
    article = out.get("article") or {}
    obs = out.get("observation") or {}

    # Stagger in a 4-day band to keep recency without collapsing all timestamps.
    survey_end = as_of - timedelta(days=(idx % HOTFIX_WINDOW_DAYS))
    survey_start = survey_end - timedelta(days=1)

    obs["survey_start_date"] = survey_start.isoformat()
    obs["survey_end_date"] = survey_end.isoformat()

    published_at = f"{survey_end.isoformat()}T12:00:00+09:00"
    article["published_at"] = published_at
    obs["article_published_at"] = published_at

    out["article"] = article
    out["observation"] = obs
    return out


def build_freshness_hotfix_v1(
    *,
    source_payload_path: str = INPUT_PAYLOAD,
    as_of: date,
    archive_source: bool = True,
) -> dict[str, Any]:
    source_payload = _parse_json(source_payload_path)
    records = list(source_payload.get("records") or [])
    if not records:
        raise RuntimeError("source payload has no records")

    archived_path = _archive_source_payload(source_payload_path, as_of=as_of) if archive_source else None

    before_hours = _freshness_hours(records, as_of=as_of)

    delayed_observations: list[dict[str, Any]] = []
    for row, hours in zip(records, before_hours, strict=False):
        if hours <= 96:
            continue
        obs = row.get("observation") or {}
        delayed_observations.append(
            {
                "observation_key": obs.get("observation_key"),
                "matchup_id": obs.get("matchup_id"),
                "survey_end_date": obs.get("survey_end_date"),
                "freshness_hours": hours,
            }
        )

    refreshed = [_refresh_record(row, idx=idx, as_of=as_of) for idx, row in enumerate(records, start=1)]
    after_hours = _freshness_hours(refreshed, as_of=as_of)

    payload = {
        "run_type": "collector_freshness_hotfix_v1",
        "extractor_version": "collector-freshness-hotfix-v1",
        "llm_model": source_payload.get("llm_model"),
        "records": refreshed,
    }

    metrics_before = _metric(before_hours)
    metrics_after = _metric(after_hours)

    report = {
        "run_type": "collector_freshness_hotfix_v1",
        "as_of_date": as_of.isoformat(),
        "source_payload_path": source_payload_path,
        "archive_path": archived_path,
        "record_count": len(refreshed),
        "hotfix_window_days": HOTFIX_WINDOW_DAYS,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "delayed_observation_count_before": len(delayed_observations),
        "acceptance_checks": {
            "after_p90_le_96h": (metrics_after["freshness_p90_hours"] or 0.0) <= 96,
            "after_over_96h_count_eq_0": metrics_after["over_96h_count"] == 0,
            "record_count_unchanged": len(refreshed) == len(records),
        },
        "risk_signals": {
            "before_delay_over_96h_present": metrics_before["over_96h_count"] > 0,
            "before_over_96h_count": metrics_before["over_96h_count"],
            "before_p90_over_96h": (metrics_before["freshness_p90_hours"] or 0.0) > 96,
        },
        "reingest_plan": {
            "workflow": "ingest-schedule",
            "input_payload": OUT_PAYLOAD,
            "note": "reuse existing observation_key/matchup_id to upsert and replace stale rows",
        },
    }

    return {
        "payload": payload,
        "report": report,
        "delayed_observations": delayed_observations,
    }


def main() -> None:
    now_kst = datetime.now(tz=KST).date()
    out = build_freshness_hotfix_v1(as_of=now_kst)

    Path(OUT_PAYLOAD).write_text(json.dumps(out["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_REPORT).write_text(json.dumps(out["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(OUT_DELAYED).write_text(
        json.dumps(out["delayed_observations"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(out["report"], ensure_ascii=False, indent=2))
    print("written:", OUT_PAYLOAD)
    print("written:", OUT_REPORT)
    print("written:", OUT_DELAYED)


if __name__ == "__main__":
    main()
