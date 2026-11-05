"""Four rows, printed-versus-inherited integers and preserved unresolved units."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_passages import (
    CALENDARS,
    DATA,
    POLICIES,
    FractionalTerm,
    load_registry,
)

ROOT = Path(__file__).parents[2]
FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-luwei-passages-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_source_pages_ambiguous_cell_images_and_runtime_data_are_fingerprinted():
    for key, digest in [
        ("source_image", "source_image_sha256"),
        ("later_note_image", "later_note_sha256"),
    ]:
        assert (
            hashlib.sha256((FIXTURE / REFERENCE[key]).read_bytes()).hexdigest()
            == REFERENCE[digest]
        )
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == REFERENCE["data_sha256"]
    for image in REFERENCE["reading_aids"]:
        assert (
            hashlib.sha256((FIXTURE / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    assert not REFERENCE["independent_second_collator"]


@pytest.mark.parametrize("case", REFERENCE["held_arithmetic_cases"])
def test_held_source_component_arithmetic_does_not_fill_all_cells_with_zero(case):
    r = load_registry().entry(
        case["calendar"], case["branch"], whole_degree_policy=case["policy"]
    )
    actual = r["literal_unit_sum_du_exact"]
    assert (F(actual) if actual is not None else None) == (
        F(case["value"]) if case["value"] is not None else None
    )
    assert r["modern_longitude"] is None and r["life_degree"] is None
    assert not r["continuous_coordinate_accepted"]


@pytest.mark.parametrize("policy", POLICIES)
def test_all48_cells_remain_separate_under_each_explicit_policy(policy):
    r = load_registry().audit(whole_degree_policy=policy)
    assert r["cells"] == 48
    assert (
        r["printed_whole_degree_cells"]
        == REFERENCE["policy_counts"]["whole_degree_printed"]
    )
    assert r["whole_degree_not_repeated_cells"] == 40
    assert (
        r["resolved_literal_sum_cells"]
        == REFERENCE["policy_counts"][policy + "_resolved"]
    )
    assert {e["calendar"] for e in r["entries"]} == set(CALENDARS)
    assert not r["full_luwei_coordinate_profile_built"]


@pytest.mark.parametrize("case", REFERENCE["partial_source_cases"])
@pytest.mark.parametrize("policy", POLICIES)
def test_ambiguous_glyph_and_bare_printed_unit_block_a_sum_in_both_policies(
    case, policy
):
    r = load_registry().entry(
        case["calendar"], case["branch"], whole_degree_policy=policy
    )
    component = r[case["component"]]
    assert component["status"] == case["status"]
    assert component["text"] == case["text"]
    assert component["value"] is None and r["literal_unit_sum_du_exact"] is None
    compared = load_registry().compare_yuanshi(
        case["calendar"], case["branch"], whole_degree_policy=policy
    )
    assert all(
        c["literal_numeric_difference_du_exact"] is None
        for c in compared["comparisons"]
    )
    assert all(not c["reference_used_to_fill_source"] for c in compared["comparisons"])


def test_printed_whole_degree_overrides_the_heading_instead_of_being_added_to_it():
    g = load_registry()
    for calendar, branch, heading, printed in [
        ("tongtian", "午", 4, 5),
        ("shoushi", "申", 7, 6),
        ("shoushi", "未", 9, 8),
    ]:
        for policy in POLICIES:
            r = g.entry(calendar, branch, whole_degree_policy=policy)
            assert r["heading_degree"] == heading
            assert r["whole_degree_used"] == printed
            assert not r["whole_degree_from_heading_interpretation"]


def test_unit_not_printed_is_distinct_from_a_printed_unit_with_a_missing_number():
    g = load_registry()
    truncated = g.entry("tongtian", "午", whole_degree_policy="explicit_only")
    assert truncated["second"]["status"] == "not_printed"
    assert truncated["unprinted_fractional_units_contributing_no_literal_term"] == [
        "抄"
    ]
    assert F(truncated["literal_unit_sum_du_exact"]) == F("5.27")
    bare = g.entry("tongtian", "辰", whole_degree_policy="inherit_column_heading")
    assert bare["second"]["status"] == "unresolved"
    assert bare["literal_unit_sum_du_exact"] is None
    odd = g.entry("shoushi", "亥", whole_degree_policy="explicit_only")
    assert odd["unprinted_fractional_units_contributing_no_literal_term"] == ["分"]
    assert F(odd["literal_unit_sum_du_exact"]) == F(12) + F(38, 10000)
    assert not odd["continuous_coordinate_accepted"]


@pytest.mark.parametrize("case", REFERENCE["comparison_hand_cases"])
def test_named_comparisons_return_differences_without_emending_luwei(case):
    r = load_registry().compare_yuanshi(
        "shoushi", case["branch"], whole_degree_policy="inherit_column_heading"
    )
    for reference in r["comparisons"]:
        assert F(reference["literal_numeric_difference_du_exact"]) == F(
            case[reference["reference_profile"] + "_difference"]
        )
        assert not reference["reference_used_to_fill_source"]
        assert not reference["difference_interpreted_as_coordinate_error"]
    assert not r["source"]["luwei_table_emended"]


def test_later_rejection_of_old_ruler_integer_is_returned_but_not_applied():
    g = load_registry()
    r = g.entry("shoushi", "卯", whole_degree_policy="inherit_column_heading")
    assert r["same_integral_degree_as_later_rejected_old_ruler_example"]
    assert not r["later_note_applied_to_change_value"]
    assert F(r["literal_unit_sum_du_exact"]) == F("2.1452")
    assert not g.entry("shoushi", "申", whole_degree_policy="inherit_column_heading")[
        "same_integral_degree_as_later_rejected_old_ruler_example"
    ]
    assert not g.entry("tongtian", "卯", whole_degree_policy="inherit_column_heading")[
        "same_integral_degree_as_later_rejected_old_ruler_example"
    ]


def test_six_earlier_explicit_cells_still_match_the_frozen_primary_observations():
    old = json.loads(
        (FIXTURE.parent / "guolao-historical-coordinates-v1/reference.json").read_text()
    )
    for case in old["luwei_comparison"]["selected_explicit_shoushi_cells"]:
        r = load_registry().entry(
            "shoushi", case["branch"], whole_degree_policy="explicit_only"
        )
        assert F(r["literal_unit_sum_du_exact"]) == F(case["degree_du"])


@pytest.mark.parametrize("value", [0.0, True, F(0), "0"])
def test_fractional_terms_reject_implicit_numerical_types(value):
    with pytest.raises(TypeError):
        FractionalTerm(value, "literal", "零")


def test_partial_units_cannot_be_backfilled_in_the_record_and_collections_are_frozen():
    with pytest.raises(ValueError):
        FractionalTerm(0, "unresolved", None)
    with pytest.raises(ValueError):
        FractionalTerm(100, "literal", "一百")
    g = load_registry()
    cells = list(g.cells)
    frozen = replace(g, cells=cells)
    cells.pop()
    assert len(frozen.cells) == 48
    with pytest.raises(ValueError):
        replace(g, cells=cells)
    with pytest.raises(ValueError):
        replace(g, cells=(g.cells[0],) * 48)
    with pytest.raises(ValueError):
        replace(g.cells[0], printed_calendar_label="授時")
    with pytest.raises(ValueError):
        g.entry("best_fit", "卯", whole_degree_policy="inherit_column_heading")
    with pytest.raises(ValueError):
        g.entry("shoushi", "卯", whole_degree_policy="assume_zero")


@pytest.mark.parametrize("policy", POLICIES)
def test_cli_can_audit_or_return_a_named_cell_without_a_modern_epoch(policy):
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/guolao/audit_guolao_passages.py"),
            "--whole-degree-policy",
            policy,
            "--calendar",
            "shoushi",
            "--branch",
            "卯",
            "--compare-yuanshi",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    r = json.loads(p.stdout)
    assert r == load_registry().compare_yuanshi(
        "shoushi", "卯", whole_degree_policy=policy
    )


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--whole-degree-policy", "explicit_only", "--calendar", "shoushi"],
        ["--whole-degree-policy", "explicit_only", "--compare-yuanshi"],
    ],
)
def test_cli_requires_explicit_degree_policy_and_a_complete_cell_selector(args):
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts/guolao/audit_guolao_passages.py"), *args],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 2 and not p.stdout
