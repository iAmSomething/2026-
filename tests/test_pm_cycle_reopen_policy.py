from __future__ import annotations

from datetime import datetime, timezone

from scripts.pm.reopen_policy import parse_bool_flag, parse_iso_datetime, select_reopen_candidates


def test_parse_bool_flag_defaults_false() -> None:
    assert parse_bool_flag(None, default=False) is False
    assert parse_bool_flag("true", default=False) is True
    assert parse_bool_flag("yes", default=False) is True
    assert parse_bool_flag("off", default=True) is False
    assert parse_bool_flag("invalid", default=False) is False


def test_select_reopen_candidates_disabled_by_default() -> None:
    issues = [
        {
            "number": 10,
            "state": "CLOSED",
            "updatedAt": "2026-02-21T10:00:00Z",
            "labels": [{"name": "status/done"}, {"name": "role/develop"}],
        }
    ]
    result = select_reopen_candidates(
        issues,
        allow_reopen_done=False,
        lookback_days=7,
        now=datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert result == []


def test_select_reopen_candidates_filters_recent_done_role_issues() -> None:
    issues = [
        {
            "number": 1,
            "state": "CLOSED",
            "updatedAt": "2026-02-21T10:00:00Z",
            "labels": [{"name": "status/done"}, {"name": "role/develop"}],
        },
        {
            "number": 2,
            "state": "CLOSED",
            "updatedAt": "2026-02-10T10:00:00Z",
            "labels": [{"name": "status/done"}, {"name": "role/develop"}],
        },
        {
            "number": 3,
            "state": "CLOSED",
            "updatedAt": "2026-02-21T10:00:00Z",
            "labels": [{"name": "status/done"}],
        },
        {
            "number": 4,
            "state": "OPEN",
            "updatedAt": "2026-02-21T10:00:00Z",
            "labels": [{"name": "status/done"}, {"name": "role/qa"}],
        },
    ]
    result = select_reopen_candidates(
        issues,
        allow_reopen_done=True,
        lookback_days=7,
        now=datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert result == [1]


def test_parse_iso_datetime_handles_z_and_naive_input() -> None:
    assert parse_iso_datetime("2026-02-21T12:00:00Z") == datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)
    assert parse_iso_datetime("2026-02-21T12:00:00") == datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)
    assert parse_iso_datetime("invalid") is None


def test_select_reopen_candidates_keeps_item_without_updated_at() -> None:
    issues = [
        {
            "number": 21,
            "state": "CLOSED",
            "updatedAt": None,
            "labels": [{"name": "status/done"}, {"name": "role/qa"}],
        },
    ]
    result = select_reopen_candidates(
        issues,
        allow_reopen_done=True,
        lookback_days=0,
        now=datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert result == [21]
