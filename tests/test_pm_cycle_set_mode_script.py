from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm" / "set_pm_cycle_mode.sh"


def _make_fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "fake_gh.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    gh_path = bin_dir / "gh"
    gh_path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
log_file="${FAKE_GH_LOG_FILE:?missing FAKE_GH_LOG_FILE}"
printf '%s\\n' "$*" >> "$log_file"
if [[ "$1" == "variable" && ( "$2" == "set" || "$2" == "delete" ) ]]; then
  exit 0
fi
echo "unexpected gh command: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    gh_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_dir, log_path


def _run_set_mode(tmp_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    bin_dir, log_path = _make_fake_gh(tmp_path)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_GH_LOG_FILE"] = str(log_path)
    proc = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc


def _read_fake_log(tmp_path: Path) -> str:
    log_path = tmp_path / "fake_gh.log"
    return log_path.read_text(encoding="utf-8") if log_path.exists() else ""


def test_offline_lane_sets_apply_defaults(tmp_path: Path) -> None:
    proc = _run_set_mode(tmp_path, ["--repo", "iAmSomething/2026-", "--lane", "offline"])
    assert proc.returncode == 0
    log = _read_fake_log(tmp_path)
    assert "variable set PM_CYCLE_MODE --repo iAmSomething/2026- --body apply" in log
    assert "variable set PM_CYCLE_MAX_CREATE --repo iAmSomething/2026- --body 4" in log
    assert "variable set PM_CYCLE_ALLOW_REOPEN_DONE --repo iAmSomething/2026- --body false" in log
    assert "variable set PM_CYCLE_REOPEN_LOOKBACK_DAYS --repo iAmSomething/2026- --body 7" in log


def test_online_lane_accepts_comment_issue_and_custom_max_create(tmp_path: Path) -> None:
    proc = _run_set_mode(
        tmp_path,
        [
            "--repo",
            "iAmSomething/2026-",
            "--lane",
            "online",
            "--max-create",
            "2",
            "--comment-issue",
            "191",
        ],
    )
    assert proc.returncode == 0
    log = _read_fake_log(tmp_path)
    assert "variable set PM_CYCLE_MODE --repo iAmSomething/2026- --body dry-run" in log
    assert "variable set PM_CYCLE_MAX_CREATE --repo iAmSomething/2026- --body 2" in log
    assert "variable set PM_CYCLE_ISSUE_NUMBER --repo iAmSomething/2026- --body 191" in log


def test_online_lane_can_clear_comment_issue_variable(tmp_path: Path) -> None:
    proc = _run_set_mode(
        tmp_path,
        ["--repo", "iAmSomething/2026-", "--lane", "online", "--clear-comment-issue"],
    )
    assert proc.returncode == 0
    log = _read_fake_log(tmp_path)
    assert "variable delete PM_CYCLE_ISSUE_NUMBER --repo iAmSomething/2026-" in log


def test_rejects_conflicting_comment_options(tmp_path: Path) -> None:
    proc = _run_set_mode(
        tmp_path,
        [
            "--repo",
            "iAmSomething/2026-",
            "--lane",
            "online",
            "--comment-issue",
            "191",
            "--clear-comment-issue",
        ],
    )
    assert proc.returncode != 0
    assert "Use either --comment-issue or --clear-comment-issue, not both." in proc.stdout
