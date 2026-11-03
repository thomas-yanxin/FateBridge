"""CI partitions retain every eligible test exactly once, after marker filtering."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_shards_cover_every_eligible_node_once(tmp_path):
    source = tmp_path / "test_cases.py"
    source.write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', range(7))\n"
        "def test_current(value):\n    assert value >= 0\n"
        "@pytest.mark.local_data\n"
        "def test_local_only():\n    raise AssertionError('local data executed')\n",
        encoding="utf-8",
    )
    reports = []
    for index in range(3):
        report = tmp_path / f"shard-{index}.json"
        code = (
            "import pytest; from pathlib import Path; "
            "from scripts.run_ci_checks import CIShard; "
            "raise SystemExit(pytest.main(['-q','-m','not local_data',"
            f"{str(source)!r}], plugins=[CIShard({index},3,Path({str(report)!r}))]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(json.loads(report.read_text()))
    collected = reports[0]["collected"]
    assert len(collected) == 7
    assert all(report["collected"] == collected for report in reports)
    selected = [node for report in reports for node in report["selected"]]
    assert len(selected) == len(set(selected)) == 7
    assert set(selected) == set(collected)
    assert not any("local_only" in node for node in selected)


@pytest.mark.parametrize("index,count", [(-1, 3), (3, 3), (0, 0)])
def test_invalid_partition_is_rejected_before_collection(index, count):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/run_ci_checks.py"),
            "--shard-index",
            str(index),
            "--shard-count",
            str(count),
            "--collect-only",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "shard-index must be in" in result.stderr
