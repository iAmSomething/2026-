from pathlib import Path
import subprocess


SCRIPT_PATH = Path("scripts/pm/comment_template.sh")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_comment_template_inserts_missing_pm_contract_keys(tmp_path: Path) -> None:
    src = tmp_path / "in.md"
    out = tmp_path / "out.md"
    src.write_text("# PM Cycle\naction summary\n", encoding="utf-8")

    proc = _run(["--kind", "pm", "--input", str(src), "--output", str(out)], cwd=Path("."))
    assert proc.returncode == 0, proc.stderr

    body = out.read_text(encoding="utf-8")
    assert "[PM AUTO][CYCLE SUMMARY]" in body
    assert "decision:" in body
    assert "next_status:" in body


def test_comment_template_validate_only_fails_without_required_keys(tmp_path: Path) -> None:
    src = tmp_path / "bad.md"
    src.write_text("[PM] update only\n", encoding="utf-8")

    proc = _run(["--kind", "pm", "--input", str(src), "--validate-only"], cwd=Path("."))
    assert proc.returncode != 0
    assert "missing key: decision:" in proc.stderr
    assert "missing key: next_status:" in proc.stderr


def test_comment_template_validate_only_passes_with_required_keys(tmp_path: Path) -> None:
    src = tmp_path / "good.md"
    src.write_text("[PM] update\ndecision: keep\nafter: note\nnext_status: status/in-progress\n", encoding="utf-8")

    proc = _run(["--kind", "pm", "--input", str(src), "--validate-only"], cwd=Path("."))
    assert proc.returncode == 0, proc.stderr
