from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import scripts.qa.run_ops_recovery_bundle as script


def _args(tmp_path: Path, *, mode: str = "dry-run") -> SimpleNamespace:
    return SimpleNamespace(
        mode=mode,
        api_base="http://127.0.0.1:8000",
        matchup_id="20260603|광역자치단체장|11-000",
        poll_fingerprint=None,
        input="data/sample_ingest.json",
        output_dir=str(tmp_path / "out"),
        report=str(tmp_path / "report.json"),
        continue_on_error=False,
        skip_ingest=False,
        skip_reprocess=False,
        skip_capture=False,
        capture_timeout=1.0,
    )


def test_run_bundle_dry_run_outputs_planned_steps(tmp_path: Path) -> None:
    args = _args(tmp_path, mode="dry-run")

    out = script.run_bundle(args)

    assert out["status"] == "dry-run"
    assert [step["status"] for step in out["steps"]] == ["planned", "planned", "planned"]
    assert Path(out["report_path"]).exists()


def test_run_bundle_apply_failure_adds_retry_guides(monkeypatch, tmp_path: Path) -> None:
    args = _args(tmp_path, mode="apply")

    def fake_run_step(*, name, mode, command, output_path=None):  # noqa: ANN001
        if name == "ingest":
            return script.StepResult(
                name=name,
                mode=mode,
                command=command,
                status="failed",
                exit_code=1,
                output_path=str(output_path) if output_path else None,
                error="timeout",
            )
        return script.StepResult(
            name=name,
            mode=mode,
            command=command,
            status="success",
            exit_code=0,
            output_path=str(output_path) if output_path else None,
        )

    monkeypatch.setattr(script, "run_step", fake_run_step)
    monkeypatch.setattr(
        script,
        "capture_endpoints",
        lambda **kwargs: script.StepResult(
            name="capture",
            mode="apply",
            command=None,
            status="failed",
            exit_code=1,
            output_path=str(tmp_path / "capture.json"),
            error="connection refused",
        ),
    )

    out = script.run_bundle(args)

    assert out["status"] == "failed"
    checklist = out["ops_checklist"]
    assert any("retry-guide: ingest 실패" in line for line in checklist)
    assert any("rollback-guide: capture 실패" in line for line in checklist)

    report = json.loads(Path(out["report_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "failed"
