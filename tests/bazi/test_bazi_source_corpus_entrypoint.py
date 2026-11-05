"""The documented direct audit command works outside the repository cwd."""

import subprocess
import sys
from pathlib import Path


def test_direct_corpus_script_can_import_its_sibling_runners_from_any_cwd(tmp_path):
    root = Path(__file__).resolve().parents[2]
    run = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/bazi/audit_bazi_source_corpus.py"),
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "--output" in run.stdout
