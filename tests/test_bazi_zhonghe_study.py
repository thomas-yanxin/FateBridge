"""A whole source block with zero fresh body labels cannot pass an adoption gate."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tests.test_bazi_seasonal_studies import frozen, historical_v5, run, study_tree
from tests.test_bazi_shuaiwang_study import shuaiwang_tree

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "tests/fixtures/bazi_seasonal_bureau_v5"


@pytest.fixture(scope="module")
def next_tree(shuaiwang_tree):
    shutil.copytree(FOLDER, shuaiwang_tree / FOLDER.relative_to(ROOT))
    for relative, expected in frozen(FOLDER / "pre-first-run.json")[
        "frozen_files"
    ].items():
        target = shuaiwang_tree / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
    return shuaiwang_tree


def test_flow_and_transcription_conflicts_do_not_supply_missing_body_labels():
    source = frozen(FOLDER / "reference.json")
    assert source["source"]["selected_pdf_pages"] == list(range(188, 202))
    assert len(source["cases"]) == 11
    fresh = [c for c in source["cases"] if c["fresh_gate_eligible"]]
    assert {c["id"] for c in fresh} == {"YL-01", "YL-02", "YL-03", "YL-04"}
    assert all(c["expected_strength"] is None for c in fresh)
    conflict = next(c for c in source["cases"] if c["id"] == "TG-04")
    assert conflict["pillars"] == ["己巳", "丁卯", "己巳", "乙未"]
    assert conflict["expected_strength"] is None


def test_full_frozen_comparison_keeps_unknowns_and_original_failed_gate(
    next_tree, tmp_path
):
    expected = frozen(
        ROOT / "docs/validation/bazi-seasonal-bureau-next-three-first-v5.json"
    )
    output = tmp_path / "result.json"
    process = run(next_tree, "audit_bazi_seasonal_bureau_v5.py", output)
    assert process.returncode == 1, process.stderr
    actual = json.loads(output.read_text())
    actual["candidate_root"] = expected["candidate_root"]
    assert actual == expected
    assert actual["production_default_changed"] is False
    assert actual["numerical_gates_passed"] is False
    assert actual["overall_score"] is None
    group = actual["groups"]["new_zhonghe_yuanliu_tongguan"]
    assert (group["cases"], group["adjudicated"], group["unknown"]) == (11, 4, 7)
    assert group["baseline_matched"] == group["candidate_matched"] == 3
