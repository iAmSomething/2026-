from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.pm.qafail_detection import has_qa_fail_report_text


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm" / "qafail_detection.py"


def run_detector(report_text: str) -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as fp:
        fp.write(report_text)
        path = fp.name
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", path],
            text=True,
            cwd=ROOT,
            check=False,
        )
        return proc.returncode
    finally:
        Path(path).unlink(missing_ok=True)


def test_detects_explicit_qa_fail_header() -> None:
    text = "[QA FAIL]\n- Verdict: FAIL\n- 원인 진단"
    assert has_qa_fail_report_text(text) is True
    assert run_detector(text) == 0


def test_ignores_qafail_token_inside_guidance_line() -> None:
    text = "- [QA PASS] / [QA FAIL] 필수 필드 템플릿을 문서에 명시"
    assert has_qa_fail_report_text(text) is False
    assert run_detector(text) == 1


def test_detects_status_fail_line() -> None:
    text = "# QA 보고서\n- Status: FAIL\n"
    assert has_qa_fail_report_text(text) is True
    assert run_detector(text) == 0


def test_ignores_backtick_qafail_token() -> None:
    text = "예시 포맷: `[QA FAIL]` 를 그대로 복붙하지 마세요."
    assert has_qa_fail_report_text(text) is False
    assert run_detector(text) == 1


def test_detects_korean_conclusion_block_line() -> None:
    text = "# QA 보고서\n- 결론 : Done 처리 불가\n"
    assert has_qa_fail_report_text(text) is True
    assert run_detector(text) == 0
