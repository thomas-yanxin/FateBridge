"""Whole-cohort checks and source-preservation attacks, not prediction samples."""

import copy
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-census-pillar-consistency-v1"
AUDIT_PATH = ROOT / "scripts/audit_bazi_census_pillar_consistency.py"
RESOLVE_PATH = ROOT / "scripts/resolve_bazi_census_pillar_inputs.py"
AUDIT = runpy.run_path(str(AUDIT_PATH))
RESOLVE = runpy.run_path(str(RESOLVE_PATH))
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def read(path):
    return json.loads(path.read_text())


def formula_flags(pillars):
    """Independent arithmetic path; the audit uses the frozen explicit tables."""
    flags = []
    parts = {}
    for name, value in pillars.items():
        if value is None:
            parts[name] = None
        elif len(value) == 2 and value[0] in STEMS and value[1] in BRANCHES:
            parts[name] = (STEMS.index(value[0]), BRANCHES.index(value[1]))
            if parts[name][0] % 2 != parts[name][1] % 2:
                flags.append(name + ":not_in_sixty_cycle")
        else:
            parts[name] = None
            flags.append(name + ":unknown_symbols_or_shape")
    if parts["year"] and parts["month"]:
        year, (month, branch) = parts["year"][0], parts["month"]
        if month != (2 * (year % 5) + 2 + (branch - 2) % 12) % 10:
            flags.append("year_month:mismatch")
    if parts["day"] and parts["hour"]:
        day, (hour, branch) = parts["day"][0], parts["hour"]
        allowed = {(2 * (day % 5) + branch) % 10}
        if branch == 0:
            allowed.add(2 * ((day + 1) % 5))
        if hour not in allowed:
            flags.append("day_hour:mismatch_all_declared_profiles")
    return flags


def test_every_original558_object_unknown_and_flag_is_retained():
    original = read(STUDY / "cases-first.json")["records"]
    report = read(STUDY / "assessment-first.json")
    assert len(original) == len(report["records"]) == 558
    assert report["counts"]["complete_literal_four_pillars"] == 530
    assert report["counts"]["partial_records_retained"] == 28
    assert report["counts"]["flagged_records"] == 11
    assert sum(report["counts"]["flags_by_relation"].values()) == 12
    assert report["all_assessable_symbolic_relations_match"] is False
    for first, actual in zip(original, report["records"], strict=True):
        assert {k: actual[k] for k in first} == first
        assert actual["symbolic_assessment"]["flags"] == formula_flags(
            first["case"]["literal_pillars"]
        )
    assert len(report["counts"]["source_kinds_retained"]) == 7
    assert report["counts"]["source_kinds_retained"]["field_not_recorded"] == 3


def test_all240_source_table_cells_and60_cycle_agree_with_independent_arithmetic():
    reference = read(STUDY / "reference-first.json")
    assert reference["all240_table_cell_differences"] == []
    assert reference["hko_table4_month"] == reference["li1947_pdf32_month"]
    assert reference["hko_table5_hour"] == reference["li1947_pdf34_35_hour"]
    assert reference["hko_table2_sexagenary_cycle"] == [
        STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)
    ]
    for i, stem in enumerate(STEMS):
        for j, branch in enumerate(BRANCHES):
            assert (
                reference["hko_table4_month"][stem][branch]
                == STEMS[(2 * (i % 5) + 2 + (j - 2) % 12) % 10]
            )
            assert (
                reference["hko_table5_hour"][stem][branch]
                == STEMS[(2 * (i % 5) + j) % 10]
            )


def test_all558_resolved_records_retain_first_objects_and_all_body_labels():
    old = read(STUDY / "cases-first.json")["records"]
    new = read(STUDY / "resolved-view-second/cases-first.json")["records"]
    report = read(STUDY / "assessment-resolved-first.json")
    assert len(old) == len(new) == len(report["records"]) == 558
    changed = []
    for first, current, assessed in zip(old, new, report["records"], strict=True):
        assert (
            first["case"]["case_id"]
            == current["case"]["case_id"]
            == assessed["case"]["case_id"]
        )
        if first["case"] != current["case"]:
            changed.append(first["case"]["case_id"])
            assert current["case_first_value_retained"] == first["case"]
            assert current["case_first_value_sha256"] == first["case_object_sha256"]
        assert {
            k: v
            for k, v in first["case"].items()
            if k not in {"anchor", "literal_pillars"}
        } == {
            k: v
            for k, v in current["case"].items()
            if k not in {"anchor", "literal_pillars"}
        }
        assert assessed["symbolic_assessment"]["flags"] == formula_flags(
            current["case"]["literal_pillars"]
        )
    assert (
        changed == read(STUDY / "correction-protocol-first.json")["corrected_case_ids"]
    )
    assert len(changed) == 8
    assert report["flagged_ids"] == ["MAIN-C219", "MAIN-C368", "MAIN-C457", "MAIN-C488"]
    assert report["counts"]["partial_records_retained"] == 28
    assert report["all_assessable_symbolic_relations_match"] is False
    assert (
        read(STUDY / "resolved-view-second/protocol-first.json")[
            "force_comparison_allowed"
        ]
        is False
    )
    for name in ["cases-first.json", "protocol-first.json", "reference-first.json"]:
        assert (STUDY / "resolved-view-first" / name).read_bytes() == (
            STUDY / "resolved-view-second" / name
        ).read_bytes()


def test_a_passing_pair_check_cannot_certify_correct_transcription():
    raw = read(STUDY / "assessment-first.json")["records"]
    corrected = read(STUDY / "assessment-resolved-first.json")["records"]
    before = next(r for r in raw if r["case"]["case_id"] == "MAIN-C514")
    after = next(r for r in corrected if r["case"]["case_id"] == "MAIN-C514")
    assert (
        before["symbolic_assessment"]["flags"]
        == after["symbolic_assessment"]["flags"]
        == []
    )
    assert before["case"]["literal_pillars"] != after["case"]["literal_pillars"]
    assert before["symbolic_assessment"]["historical_birth_moment_identified"] is False


@pytest.mark.parametrize(
    "hour,expected_flag",
    [("丙子", False), ("戊子", False), ("庚子", True), ("己丑", True)],
)
def test_zi_profiles_are_separate_and_cannot_rescue_other_hour_mismatches(
    hour, expected_flag
):
    reference = read(STUDY / "reference-first.json")
    record = {
        "case": {
            "literal_pillars": {
                "year": "甲子",
                "month": "丙寅",
                "day": "乙丑",
                "hour": hour,
            },
            "kind": "source_counterfactual_relational_case",
        }
    }
    first = copy.deepcopy(record)
    assessment = AUDIT["assess_record"](record, reference)["symbolic_assessment"]
    assert bool(assessment["flags"]) is expected_flag
    assert record == first
    assert assessment["day_hour"]["actual_early_or_late_zi_clock_identified"] is False


def test_missing_pillars_are_never_filled_or_suppressed():
    reference = read(STUDY / "reference-first.json")
    record = {
        "case": {"literal_pillars": dict.fromkeys(["year", "month", "day", "hour"])}
    }
    result = AUDIT["assess_record"](record, reference)
    assert result["case"] == record["case"]
    assert result["symbolic_assessment"]["year_month"]["status"].startswith(
        "not_assessable"
    )
    assert result["symbolic_assessment"]["day_hour"]["status"].startswith(
        "not_assessable"
    )
    assert result["symbolic_assessment"]["complete_literal_four_pillars"] is False


@pytest.mark.parametrize(
    "mutation", ["grade", "wrong_first_value", "bad_evidence", "repeat", "caption"]
)
def test_correction_bounds_refuse_unrelated_edits_and_retain_input_on_failure(mutation):
    original = read(STUDY / "cases-first.json")
    edits = read(STUDY / "case-input-corrections-first.json")
    before = copy.deepcopy(original)
    if mutation == "grade":
        edits["records"][0]["expected_daymaster_strength"] = "强"
    elif mutation == "wrong_first_value":
        edits["records"][0]["before_literal_pillars"]["day"] = "甲子"
    elif mutation == "bad_evidence":
        edits["records"][0]["evidence"][0]["sha256"] = "0" * 64
    elif mutation == "repeat":
        edits["records"].append(copy.deepcopy(edits["records"][0]))
    else:
        edits["records"][0]["after_anchor"] = "unrelated actor or claim"
    with pytest.raises(ValueError):
        RESOLVE["apply_corrections"](original, edits, ROOT)
    assert original == before


def test_complete_actual_cli_replays_all558_and_keeps_failure_exit(tmp_path):
    generated = tmp_path / "resolved"
    process = subprocess.run(
        [sys.executable, str(RESOLVE_PATH), "--output-directory", str(generated)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    assert (generated / "cases-first.json").read_bytes() == (
        STUDY / "resolved-view-second/cases-first.json"
    ).read_bytes()
    result = tmp_path / "assessment.json"
    process = subprocess.run(
        [
            sys.executable,
            str(AUDIT_PATH),
            "--study",
            str(generated),
            "--output",
            str(result),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 1, process.stderr
    assert (
        result.read_bytes() == (STUDY / "assessment-resolved-first.json").read_bytes()
    )
    before = result.read_bytes()
    process = subprocess.run(
        [sys.executable, str(AUDIT_PATH), "--output", str(result)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0 and result.read_bytes() == before


def test_changed_full_inventory_refuses_to_emit_a_receipt(tmp_path):
    study = tmp_path / "corrupt"
    study.mkdir()
    for name in [
        "protocol-first.json",
        "protocol-first.sha256",
        "cases-first.json",
        "reference-first.json",
        "reference-first.sha256",
    ]:
        shutil.copyfile(STUDY / name, study / name)
    inventory = read(study / "cases-first.json")
    inventory["records"].pop()
    (study / "cases-first.json").write_text(json.dumps(inventory))
    output = tmp_path / "should-not-exist.json"
    result = subprocess.run(
        [
            sys.executable,
            str(AUDIT_PATH),
            "--study",
            str(study),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and not output.exists()
