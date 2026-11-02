"""Frozen source labels, full historical replay and non-adoption boundaries."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_bazi_clash_source_studies import historical_v5

ROOT = Path(__file__).resolve().parents[1]


def frozen(path):
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(path.read_text())


def test_next_complete_unit_reuses_exact_candidate_without_reading_forward_for_favorable_cases():
    previous = ROOT / "tests/fixtures/bazi_seasonal_bureau_v3"
    following = ROOT / "tests/fixtures/bazi_seasonal_bureau_v4"
    protocol = frozen(following / "protocol.json")
    assert (following / "candidate-core.py.txt").read_bytes() == (
        previous / "candidate-core.py.txt"
    ).read_bytes()
    assert protocol["source_plan"]["selected_pdf_pages"] == list(range(175, 189))
    assert protocol["production_default_changed"] is False
    assert protocol["overall_score"] is None
    assert (
        protocol["study_status"]
        == "candidate_unchanged_complete_shuaiwang_block_frozen_not_yet_collected_or_compared"
    )


@pytest.fixture(scope="module")
def study_tree(historical_v5):
    for version in (2, 3):
        folder = ROOT / f"tests/fixtures/bazi_seasonal_bureau_v{version}"
        target = historical_v5 / folder.relative_to(ROOT)
        shutil.copytree(folder, target)
        for relative, expected in frozen(folder / "pre-first-run.json")[
            "frozen_files"
        ].items():
            destination = historical_v5 / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected
        for relative, expected in frozen(folder / "runner-repair-v2.json")[
            "frozen_files"
        ].items():
            destination = historical_v5 / relative
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected
    return historical_v5


def run(tree, script, output, candidate=None):
    return subprocess.run(
        [
            sys.executable,
            str(tree / "scripts" / script),
            "--candidate-root",
            str(candidate or tree),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_complete_content_boundaries_unknowns_and_standalone_old_fixture_are_frozen():
    first = frozen(ROOT / "tests/fixtures/bazi_seasonal_bureau_v2/reference.json")
    second = frozen(ROOT / "tests/fixtures/bazi_seasonal_bureau_v3/reference.json")
    assert first["source"]["selected_pdf_pages"] == list(range(150, 161))
    assert second["source"]["selected_pdf_pages"] == list(range(160, 176))
    assert len(first["cases"]) == 10 and len(second["cases"]) == 8
    assert sum(c["fresh_gate_eligible"] for c in first["cases"]) == 9
    assert sum(c["fresh_gate_eligible"] for c in second["cases"]) == 7
    assert sum(c["expected_strength"] is not None for c in first["cases"]) == 2
    assert sum(c["expected_strength"] is not None for c in second["cases"]) == 5
    assert (
        "tests/fixtures/bazi-strength-reference.json" in first["overlap_source_hashes"]
    )
    assert (
        "tests/fixtures/bazi_seasonal_bureau_v2/reference.json"
        in second["overlap_source_hashes"]
    )
    assert next(c for c in first["cases"] if c["id"] == "FJ-11-TAIL")["pillars"] == [
        "庚寅",
        "己卯",
        "乙亥",
        "癸未",
    ]
    assert next(c for c in first["cases"] if c["id"] == "BG-05")[
        "source_pdf_pages"
    ] == [154, 155]
    assert next(c for c in second["cases"] if c["id"] == "ML-02")[
        "source_pdf_pages"
    ] == [172, 173]
    for cid in ["BG-01", "BG-04", "BG-09"]:
        assert (
            next(c for c in first["cases"] if c["id"] == cid)["expected_strength"]
            is None
        )
    assert (
        next(c for c in second["cases"] if c["id"] == "ML-01")["expected_strength"]
        is None
    )


@pytest.mark.parametrize(
    "version,script,report",
    [
        (
            2,
            "audit_bazi_seasonal_bureau_v2.py",
            "bazi-seasonal-bureau-first-complete-v2.json",
        ),
        (
            3,
            "audit_bazi_seasonal_bureau_v3.py",
            "bazi-seasonal-bureau-next-four-first-v3.json",
        ),
    ],
)
def test_original_full_comparisons_replay_without_relabeling_or_promoting_known_improvement(
    version, script, report, study_tree, tmp_path
):
    expected = frozen(ROOT / "docs/validation" / report)
    path = tmp_path / "replay.json"
    process = run(study_tree, script, path)
    assert process.returncode == 1, process.stderr
    result = json.loads(path.read_text())
    result["candidate_root"] = expected["candidate_root"]
    assert result == expected
    assert not result["adoption_gates"][
        "new_nonoverlap_explicit_body_or_formation_improvement"
    ]
    assert result["classical_acceptance_passed"] is False
    assert result["production_default_changed"] is False
    assert result["overall_score"] is None
    assert result["groups"]["prior_shape_bureau"]["resolved"] == ["FJ-08"]


def test_first_missing_identifier_failure_is_retained_and_reproducible(
    study_tree, tmp_path
):
    failure = frozen(
        ROOT / "docs/validation/bazi-seasonal-bureau-first-failure-v1.json"
    )
    assert failure["comparison_completed"] is False
    assert failure["new_source_group_reached"] is False
    output = tmp_path / "failure-output.json"
    process = run(study_tree, "audit_bazi_seasonal_bureau.py", output)
    assert process.returncode == 1 and "KeyError: 'id'" in process.stderr
    assert not output.exists()


def test_more_source_groups_retain_new_failures_instead_of_calling_all_weak_neutral_strong_words_truth():
    result = frozen(
        ROOT / "docs/validation/bazi-seasonal-bureau-next-four-first-v3.json"
    )
    source = result["groups"]["new_body_spirit_month_hour"]
    assert (
        source["adjudicated"],
        source["baseline_matched"],
        source["candidate_matched"],
    ) == (5, 3, 3)
    mismatches = {r["id"] for r in source["rows"] if r["baseline_matches"] is False}
    assert mismatches == {"SP-02", "ML-02"}
    changed = next(r for r in source["rows"] if r["id"] == "BG-09-TAIL")
    assert changed["expected_strength"] is None
    assert changed["changed"] is True and changed["candidate_matches"] is None
    assert changed["resolved"] is False


def test_changing_transitive_source_outside_the_eight_numeric_pins_still_fails(
    study_tree, tmp_path
):
    candidate = tmp_path / "bad-candidate"
    shutil.copytree(study_tree / "src", candidate / "src")
    shutil.copy2(study_tree / "uv.lock", candidate / "uv.lock")
    path = candidate / "src/fatebridge/core/root_qualification.py"
    path.write_bytes(path.read_bytes() + b"\n# changed\n")
    output = tmp_path / "forbidden.json"
    process = run(study_tree, "audit_bazi_seasonal_bureau_v2.py", output, candidate)
    assert (
        process.returncode == 1 and "Full historical source differs" in process.stderr
    )
    assert not output.exists()


def test_normalization_cannot_fill_a_missing_body_label_even_if_its_local_hash_is_changed(
    study_tree, tmp_path
):
    tree = tmp_path / "tampered"
    shutil.copytree(study_tree, tree)
    folder = tree / "tests/fixtures/bazi_seasonal_bureau_v2"
    p = folder / "normalized-month-cautions.json"
    d = json.loads(p.read_text())
    d["cases"][0]["expected_strength"] = "强"
    p.write_text(json.dumps(d))
    repair = folder / "runner-repair-v2.json"
    r = json.loads(repair.read_text())
    r["frozen_files"][
        "tests/fixtures/bazi_seasonal_bureau_v2/normalized-month-cautions.json"
    ] = hashlib.sha256(p.read_bytes()).hexdigest()
    repair.write_text(json.dumps(r))
    repair.with_suffix(".sha256").write_text(
        hashlib.sha256(repair.read_bytes()).hexdigest() + "\n"
    )
    output = tmp_path / "forbidden-label.json"
    process = run(tree, "audit_bazi_seasonal_bureau_v2.py", output)
    assert (
        process.returncode == 1
        and "Normalization changed more than stable record identifiers"
        in process.stderr
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "script", ["audit_bazi_seasonal_bureau_v2.py", "audit_bazi_seasonal_bureau_v3.py"]
)
def test_existing_comparison_is_never_overwritten(script, study_tree, tmp_path):
    output = tmp_path / "keep.json"
    output.write_text("preserve exact first bytes")
    process = run(study_tree, script, output)
    assert (
        process.returncode == 2 and output.read_text() == "preserve exact first bytes"
    )
