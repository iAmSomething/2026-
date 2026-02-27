from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm" / "worktree_hygiene.sh"


def _touch_with_age(path: Path, *, now_epoch: int, age_hours: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    epoch = now_epoch - (age_hours * 3600)
    os.utime(path, (epoch, epoch))


def _worktree_list_file(base_dir: Path, active_paths: list[Path]) -> Path:
    file_path = base_dir / "worktree_list.txt"
    lines: list[str] = []
    for path in active_paths:
        lines.append(f"worktree {path}")
        lines.append("HEAD dummy")
        lines.append("branch refs/heads/main")
        lines.append("")
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


def _run_script(base_dir: Path, report_path: Path, worktree_list: Path, mode: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKTREE_HYGIENE_NOW_EPOCH"] = "2000000000"
    env["WORKTREE_HYGIENE_WORKTREE_LIST_FILE"] = str(worktree_list)
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--mode",
            mode,
            "--hours",
            "24",
            "--base-dir",
            str(base_dir),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_worktree_hygiene_dry_run_detects_only_stale_non_active_paths(tmp_path: Path) -> None:
    now_epoch = 2_000_000_000
    base_dir = tmp_path / "scan"
    base_dir.mkdir(parents=True, exist_ok=True)

    protected_main = base_dir / "election2026_codex"
    stale_candidate = base_dir / "election2026_codex_issue_stale"
    active_candidate = base_dir / "election2026_codex_issue_active"
    stale_runtime = base_dir / "election2026_runtime_old"

    _touch_with_age(protected_main, now_epoch=now_epoch, age_hours=72)
    _touch_with_age(stale_candidate, now_epoch=now_epoch, age_hours=72)
    _touch_with_age(active_candidate, now_epoch=now_epoch, age_hours=72)
    _touch_with_age(stale_runtime, now_epoch=now_epoch, age_hours=72)

    worktree_list = _worktree_list_file(base_dir, [protected_main, active_candidate])
    report_path = base_dir / "report_dry_run.txt"
    proc = _run_script(base_dir, report_path, worktree_list, "dry-run")

    assert proc.returncode == 0
    report = report_path.read_text(encoding="utf-8")
    assert "candidate_count=2" in report
    assert str(stale_candidate) in report
    assert str(stale_runtime) in report
    assert f"{active_candidate}|active_worktree" in report
    assert f"{protected_main}|protected_root" in report


def test_worktree_hygiene_apply_removes_only_guarded_candidates(tmp_path: Path) -> None:
    now_epoch = 2_000_000_000
    base_dir = tmp_path / "scan"
    base_dir.mkdir(parents=True, exist_ok=True)

    stale_candidate = base_dir / "election2026_codex_issue_remove_me"
    active_candidate = base_dir / "election2026_codex_issue_keep_me"
    stale_runtime = base_dir / "election2026_runtime_remove_me"

    _touch_with_age(stale_candidate, now_epoch=now_epoch, age_hours=96)
    _touch_with_age(active_candidate, now_epoch=now_epoch, age_hours=96)
    _touch_with_age(stale_runtime, now_epoch=now_epoch, age_hours=96)

    worktree_list = _worktree_list_file(base_dir, [active_candidate])
    report_path = base_dir / "report_apply.txt"
    proc = _run_script(base_dir, report_path, worktree_list, "apply")

    assert proc.returncode == 0
    assert not stale_candidate.exists()
    assert not stale_runtime.exists()
    assert active_candidate.exists()

    report = report_path.read_text(encoding="utf-8")
    assert "candidate_count=2" in report
    assert "deleted_count=2" in report
    assert "error_count=0" in report
    assert str(active_candidate) not in report.split("[deleted]", 1)[1]
