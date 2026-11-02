"""Symbolic dependency checks and preserved source conflicts, not efficacy data."""

import copy
import json
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-source-contrast-dependencies-v1"
AUDIT = runpy.run_path(str(ROOT / "scripts/audit_bazi_source_contrast_dependencies.py"))
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def read(path):
    return json.loads(path.read_text())


def test_all15_printed_pairs_and14_unprinted_records_remain():
    result = AUDIT["assess"](STUDY, ROOT)
    assert len(result["selected_claims"]) == 17
    assert len(result["selected_cases"]) == 30
    assert len(result["printed_pair_results"]) == 15
    assert len(result["all14_unprinted_relational_cases_retained"]) == 14
    for row in result["all14_unprinted_relational_cases_retained"]:
        assert not any(row["literal_pillars"].values())
    assert len(result["all_original_questions_retained"]["original22"]) == 22
    assert len(result["all_original_questions_retained"]["input4"]) == 4
    assert result["source_ambiguities_closed"] == 0
    assert not result["force_comparison_allowed"] and not result["causal_acceptance"]


def test_all15_counts_against_independent_character_positions():
    result = read(STUDY / "assessment-second.json")
    keys = ["year", "month", "day", "hour"]
    for row in result["printed_pair_results"]:
        left = "".join(row["before_case"]["literal_pillars"][k] for k in keys)
        right = "".join(row["after_case"]["literal_pillars"][k] for k in keys)
        differing = {
            i for i, (a, b) in enumerate(zip(left, right, strict=True)) if a != b
        }
        actual = row["symbolic_contrast"]
        assert actual["literal_glyph_change_count"] == len(differing)
        assert actual["non_derived_coordinate_change_count"] == len(differing - {2, 6})
        assert len(actual["changed_derived_fields"]) == len(differing & {2, 6})
        assert not actual["single_variable_causal_experiment_certified"]
        assert not actual["historical_calendar_realisability_certified"]


def test_all240_correspondences_against_independent_arithmetic():
    reference = read(STUDY / "reference-first.json")
    for i, stem in enumerate(STEMS):
        for j, branch in enumerate(BRANCHES):
            month = STEMS[(2 * (i % 5) + 2 + (j - 2) % 12) % 10]
            values = {
                "year": stem + "子",
                "month": month + branch,
                "day": "甲子",
                "hour": "甲子",
            }
            checked = AUDIT["stem_checks"](
                AUDIT["parts"](values), reference, "ordinary"
            )
            assert checked["month.stem"] == {
                "observed": month,
                "expected": month,
                "matches": True,
            }
            hour = STEMS[(2 * (i % 5) + j) % 10]
            values.update(day=stem + "子", hour=hour + branch)
            checked = AUDIT["stem_checks"](
                AUDIT["parts"](values), reference, "ordinary"
            )
            assert checked["hour.stem"] == {
                "observed": hour,
                "expected": hour,
                "matches": True,
            }


def test_four_linked_change_examples_preserve_two_literal_changes():
    rows = {
        r["after_case_id"]: r["symbolic_contrast"]
        for r in read(STUDY / "assessment-second.json")["printed_pair_results"]
    }
    for identity in ["MAIN-C097", "MAIN-C103", "MAIN-C202", "MAIN-C363"]:
        assert rows[identity]["literal_glyph_change_count"] == 2
        assert rows[identity]["non_derived_coordinate_change_count"] == 1
        assert len(rows[identity]["changed_derived_fields"]) == 1
    assert rows["MAIN-C394"]["literal_glyph_change_count"] == 3
    assert rows["MAIN-C394"]["non_derived_coordinate_change_count"] == 2
    assert rows["MAIN-C047"]["non_derived_coordinate_change_count"] == 4


def test_same_glyph_bag_does_not_mean_same_positions():
    row = next(
        r
        for r in read(STUDY / "assessment-second.json")["printed_pair_results"]
        if r["after_case_id"] == "MAIN-C451"
    )
    actual = row["symbolic_contrast"]
    assert actual["same_glyph_multiset"]
    assert (
        actual["literal_glyph_change_count"]
        == actual["non_derived_coordinate_change_count"]
        == 2
    )


def test_invalid_derived_only_change_cannot_be_explained_away():
    reference = read(STUDY / "reference-first.json")
    left = {"year": "己卯", "month": "丁卯", "day": "壬午", "hour": "甲辰"}
    right = {**left, "hour": "丙辰"}
    result = AUDIT["compare"](left, right, reference)
    assert result["literal_glyph_change_count"] == 1
    assert result["non_derived_coordinate_change_count"] == 0
    assert not any(
        p["all_observed_stems_match_tables"] for p in result["profile_candidates"]
    )
    assert not result["profile_candidates"][0]["changed_derived_field_checks"][0][
        "after_matches"
    ]


def test_sixty_cycle_and_table_consistency_are_separate_checks():
    reference = read(STUDY / "reference-first.json")
    left = {"year": "甲子", "month": "丙寅", "day": "甲子", "hour": "甲子"}
    result = AUDIT["compare"](left, {**left, "year": "甲丑"}, reference)
    assert result["sixty_cycle_mismatches"]["after"] == ["year"]
    assert result["profile_candidates"][0]["all_observed_stems_match_tables"]
    assert not result["historical_calendar_realisability_certified"]


def test_partial_input_does_not_gain_missing_coordinates():
    reference = read(STUDY / "reference-first.json")
    left = {"year": "甲子", "month": "丙寅", "day": "甲子", "hour": None}
    before = copy.deepcopy(left)
    result = AUDIT["compare"](left, left, reference)
    assert result["literal_glyph_change_count"] is None
    assert result["non_derived_coordinate_change_count"] is None
    assert result["unknown_coordinates_retained"] == ["hour.stem", "hour.branch"]
    assert left == before


def test_all_zi_profile_combinations_retained_without_clock_choice():
    reference = read(STUDY / "reference-first.json")
    left = {"year": "甲子", "month": "丙寅", "day": "甲子", "hour": "甲子"}
    right = {**left, "day": "丙子", "hour": "戊子"}
    result = AUDIT["compare"](left, right, reference)
    assert len(result["profile_candidates"]) == 4
    assert (
        sum(p["all_observed_stems_match_tables"] for p in result["profile_candidates"])
        == 1
    )
    assert not result["actual_zi_clock_inferred"]


def test_first_analysis_kept_with_only_predeclared_added_fields():
    first = read(STUDY / "assessment-first.json")
    second = read(STUDY / "assessment-second.json")
    second["runner_sha256"] = first["runner_sha256"]
    for row in second["printed_pair_results"]:
        assert row["symbolic_contrast"].pop("sixty_cycle_mismatches") == {
            "before": [],
            "after": [],
        }
    assert first == second


def test_omitted_source_pair_caught_even_if_review_and_plan_hashes_rebound(tmp_path):
    for path in STUDY.glob("*.json"):
        shutil.copyfile(path, tmp_path / path.name)
    for path in STUDY.glob("*.sha256"):
        shutil.copyfile(path, tmp_path / path.name)
    plan = read(tmp_path / "pair-link-plan-first.json")
    review = read(tmp_path / "pair-source-review-first.json")
    plan["printed_pairs"].pop(11)
    review["printed_pairs"].pop(11)
    for name, value in [
        ("pair-link-plan-first.json", plan),
        ("pair-source-review-first.json", review),
    ]:
        path = tmp_path / name
        if name.startswith("pair-source"):
            value["pair_link_plan_sha256"] = AUDIT["sha"](
                tmp_path / "pair-link-plan-first.json"
            )
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        path.with_suffix(".sha256").write_text(AUDIT["sha"](path) + "\n")
    with pytest.raises(ValueError, match="Selected source contrasts omitted"):
        AUDIT["assess"](tmp_path, ROOT)
