from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm" / "qapass_detection.py"


def run_detector(issue_json: dict) -> int:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "issue-json"],
        input=json.dumps(issue_json, ensure_ascii=False),
        text=True,
        cwd=ROOT,
        check=False,
    )
    return proc.returncode


def run_detector_comments_array(comment_bodies: list[str]) -> int:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "comments-array"],
        input=json.dumps(comment_bodies, ensure_ascii=False),
        text=True,
        cwd=ROOT,
        check=False,
    )
    return proc.returncode


def test_detects_real_qa_pass_comment() -> None:
    payload = {
        "comments": [
            {"body": "중간 점검"},
            {"body": "[QA PASS]\n- 회귀 테스트 통과"},
        ]
    }
    assert run_detector(payload) == 0


def test_ignores_guidance_text_with_qapass_token() -> None:
    payload = {
        "comments": [
            {"body": "안내: status/done 전환 전 [QA PASS] 코멘트를 남겨주세요."},
        ]
    }
    assert run_detector(payload) == 1


def test_ignores_backtick_qapass_token() -> None:
    payload = {
        "comments": [
            {"body": "예시 포맷: `[QA PASS]` 를 그대로 복붙하지 마세요."},
        ]
    }
    assert run_detector(payload) == 1


def test_detects_qapass_in_comments_array_mode() -> None:
    payload = [
        "중간 안내 코멘트",
        "[QA PASS]\n- 계약/API/스모크 PASS",
    ]
    assert run_detector_comments_array(payload) == 0


def test_ignores_inline_qapass_not_at_line_start() -> None:
    payload = {
        "comments": [
            {"body": "검수 결론: [QA PASS] 로 처리 예정"},
        ]
    }
    assert run_detector(payload) == 1
