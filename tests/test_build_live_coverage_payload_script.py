from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qa" / "build_live_coverage_payload.sh"


def _write_generator(path: Path, payload_path: Path, marker: str) -> None:
    path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                f'Path(r"{payload_path}").write_text("{marker}", encoding="utf-8")',
            ]
        ),
        encoding="utf-8",
    )


def test_prefers_v2_and_writes_canonical_payload(tmp_path: Path) -> None:
    v2_script = tmp_path / "v2.py"
    v1_script = tmp_path / "v1.py"
    v2_payload = tmp_path / "v2_payload.json"
    v1_payload = tmp_path / "v1_payload.json"
    canonical_payload = tmp_path / "canonical_payload.json"

    _write_generator(v2_script, v2_payload, "from-v2")
    _write_generator(v1_script, v1_payload, "from-v1")

    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--python",
            sys.executable,
            "--v2-script",
            str(v2_script),
            "--v1-script",
            str(v1_script),
            "--v2-payload",
            str(v2_payload),
            "--v1-payload",
            str(v1_payload),
            "--canonical-payload",
            str(canonical_payload),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "generator=v2" in proc.stdout
    assert canonical_payload.read_text(encoding="utf-8") == "from-v2"


def test_falls_back_to_v1_when_v2_is_missing(tmp_path: Path) -> None:
    v2_script = tmp_path / "v2_missing.py"
    v1_script = tmp_path / "v1.py"
    v1_payload = tmp_path / "v1_payload.json"
    canonical_payload = tmp_path / "canonical_payload.json"

    _write_generator(v1_script, v1_payload, "from-v1")

    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--python",
            sys.executable,
            "--v2-script",
            str(v2_script),
            "--v1-script",
            str(v1_script),
            "--v1-payload",
            str(v1_payload),
            "--canonical-payload",
            str(canonical_payload),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "generator=v1" in proc.stdout
    assert canonical_payload.read_text(encoding="utf-8") == "from-v1"


def test_exits_nonzero_when_no_generator_script_exists(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--python",
            sys.executable,
            "--v2-script",
            str(tmp_path / "not_found_v2.py"),
            "--v1-script",
            str(tmp_path / "not_found_v1.py"),
            "--canonical-payload",
            str(tmp_path / "canonical_payload.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "no generator found" in proc.stderr
