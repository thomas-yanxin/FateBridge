"""CI partitions retain every eligible test exactly once, after marker filtering."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


def test_repository_helpers_precede_dependency_tests_module(tmp_path):
    (tmp_path / "tests.py").write_text(
        "raise AssertionError('dependency tests module imported')\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-c", "import tests.support; import tests.fixtures"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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
    weights = {
        "test_cases.py::test_current[0]": 99,
        "test_cases.py::test_current[1]": 98,
    }
    for index in range(3):
        report = tmp_path / f"shard-{index}.json"
        code = (
            "import pytest; from pathlib import Path; "
            "from scripts.ci_sharding import CIShard; "
            "raise SystemExit(pytest.main(['-q','-m','not local_data',"
            f"'--rootdir',{str(tmp_path)!r},"
            f"{str(source)!r}], plugins=[CIShard({index},3,Path({str(report)!r}),weights={weights!r})]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[2],
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
    for report in reports:
        assert report["selected"] == [
            node for node in collected if node in report["selected"]
        ]
        assert len(set(report["selected"]) & set(weights)) <= 1
    assert set(weights) <= set(collected)


def test_invalid_partition_is_rejected_before_collection():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/run_ci_checks.py"),
            "--shard-index",
            "3",
            "--shard-count",
            "3",
            "--collect-only",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 4
    assert "shard-index must be in" in result.stderr


def test_distributed_workers_write_one_intact_coverage_report(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "test_cases.py"
    source.write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', range(9))\n"
        "def test_current(value):\n    assert value >= 0\n"
        "@pytest.mark.local_data\n"
        "def test_local_only():\n    raise AssertionError('local data executed')\n",
        encoding="utf-8",
    )
    report = tmp_path / "selection.json"
    junit = tmp_path / "results.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "scripts.ci_sharding",
            "-p",
            "xdist.plugin",
            "-n",
            "2",
            "--dist",
            "worksteal",
            "--rootdir",
            str(tmp_path),
            "-m",
            "not local_data",
            "--shard-index",
            "1",
            "--shard-count",
            "3",
            "--selection-report",
            str(report),
            "--junitxml",
            str(junit),
            str(source),
        ],
        cwd=root,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    coverage = json.loads(report.read_text())
    assert len(coverage["collected"]) == 9
    assert len(coverage["selected"]) == 3
    cases = list(ET.parse(junit).iter("testcase"))
    executed = [f"test_cases.py::{case.get('name')}" for case in cases]
    assert len(executed) == len(set(executed)) == 3
    assert set(executed) == set(coverage["selected"])
