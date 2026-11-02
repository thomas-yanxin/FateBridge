"""Repairing runtime access must not rewrite any original batch's grades."""

import ast
import json
import tarfile
from pathlib import Path

import pytest

from scripts.evaluate_agent import grade

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_every_original_case_replays_the_same_mechanical_grade(version):
    folder = ROOT / f"tests/fixtures/bazi_semantic_run_v{version}"
    cases = json.loads((folder / "case-dataset.json").read_text())["cases"]
    original = json.loads((folder / "report.json").read_text())["cases"]
    for case, before in zip(cases, original, strict=True):
        path = folder / case["id"]
        events = [
            json.loads(line)
            for line in (path / "events.jsonl").read_text().splitlines()
        ]
        current = grade(
            case, events, (path / "answer.txt").read_text(), before["exit_code"]
        )
        assert current["failures"] == before["failures"]
        assert current["mechanical_checks_passed"] == before["mechanical_checks_passed"]


def test_existing_scorer_and_argument_comparison_logic_are_unchanged():
    with tarfile.open(
        ROOT / "tests/fixtures/bazi_semantic_run_v1/runtime-source.tar.gz"
    ) as archive:
        old = archive.extractfile("scripts/evaluate_agent.py").read().decode()
    new = (ROOT / "scripts/evaluate_agent.py").read_text()

    def gates(text):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(text).body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"grade", "observations", "_same_argument_path"}
        }

    assert gates(old) == gates(new)
