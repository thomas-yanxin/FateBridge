"""Independent given-input calculations retain both source witnesses and failures."""

import copy
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.audit_jyotish_drik_editions import (
    PLANETS,
    build_report,
    compare_native,
    given_inputs,
    parts_from_clauses,
    value_from_clauses,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/jyotish-raman-1942-drik-primary.json"
PRIMARY = json.loads(FIXTURE.read_text())
LATER = json.loads((ROOT / "tests/fixtures/jyotish-drik-primary.json").read_text())


def test_primary_seal_full_orientation_and_all_blank_cells_are_retained():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == "75cadbe69b04879713abf926df488888980e10996ba91a7adc01fbe741c8c49a"
    )
    report = build_report(PRIMARY, LATER)
    assert report["matrix_slots_count"] == 49
    assert report["literal_angle_cells"] == report["literal_signed_cells"] == 29
    assert report["blank_angle_cells"] == 20
    assert len(report["literal_signed_term_relations"]) == 31
    assert all(
        x["angle_blank_domain_ok"]
        for x in report["matrix_slots"]
        if x["angle_blank_domain_ok"] is not None
    )
    assert all(
        x["blank_agrees_with_zero"]
        for x in report["matrix_slots"]
        if x["printed_terms"] is None
    )


def test_literal225_is_not_silently_replaced_by_header255_or_later_input():
    report = build_report(PRIMARY, LATER)
    assert report["angle_conflicts"] == [
        dict(
            target="Saturn",
            aspector="Mars",
            header_difference="7651/30",
            printed_angle="6751/30",
            difference_arcminutes="-1800",
            equal=False,
        )
    ]
    row = next(
        x
        for x in report["matrix_slots"]
        if x["target"] == "Saturn" and x["aspector"] == "Mars"
    )
    assert row["exact_signed"] == "-1349/60"
    assert row["signed_formula_from_printed_angle"] == "-3149/60"
    assert row["printed_terms"] == ["-22.5"]


def test_given_formula_parts_preserve_signed_split_special_cells():
    report = build_report(PRIMARY, LATER)
    rows = [
        x
        for x in report["literal_signed_term_relations"]
        if x["target"] == "Mars" and x["aspector"] == "Jupiter"
    ]
    assert [x["printed"] for x in rows] == ["30", "3.8"]
    assert [x["role"] for x in rows] == ["special", "ordinary"]
    assert [x["exact_header_formula"] for x in rows] == ["30", "113/30"]
    assert parts_from_clauses("Jupiter", Fraction(120) + Fraction(1, 60), PRIMARY) == (
        Fraction(1799, 60),
        30,
    )


def test_all_decimal_failures_and_competing_display_readings_remain_visible():
    report = build_report(PRIMARY, LATER)
    assert len(report["decimal_relations"]) == 42
    assert len(report["decimal_conflicts"]) == 14
    sums = [
        x
        for x in report["decimal_conflicts"]
        if x["relation"] == "example54_sum_of_literal_terms"
    ]
    assert [(x["target"], Fraction(x["difference"])) for x in sums] == [
        ("Sun", Fraction("-0.3")),
        ("Moon", Fraction("-0.6")),
    ]
    carry = [
        x for x in report["decimal_conflicts"] if x["relation"] == "example55_to56_drik"
    ]
    assert [(x["target"], x["printed"]) for x in carry] == [("Mars", "5.350")]
    for label, failures in [
        ("exact_quarter", 5),
        ("quarter_half_up", 5),
        ("quarter_toward_zero", 1),
    ]:
        assert (
            sum(
                x["relation"] == "example55_" + label
                for x in report["decimal_conflicts"]
            )
            == failures
        )
    terms = report["literal_signed_term_relations"]
    disputed = [
        x
        for x in terms
        if x["printed"]
        not in (x["half_up_at_printed_quantum"], x["toward_zero_at_printed_quantum"])
    ]
    assert [(x["aspector"], x["target"]) for x in disputed] == [
        ("Jupiter", "Sun"),
        ("Saturn", "Sun"),
        ("Mars", "Moon"),
        ("Mercury", "Jupiter"),
    ]
    assert not report["complete_single_original_accepted"]
    assert not report["production_activation_eligible"]
    assert report["independent_real_event_cases"] == 0


def test_positive_earlier_mercury_columns_never_adjudicate_arbitrary_association():
    report = build_report(PRIMARY, LATER)
    cross = report["cross_witness"]
    assert cross["earlier_mercury_given_sign"] == "benefic"
    assert cross["later_mercury_given_sign"] == "malefic"
    assert cross["all_seven_heading_inputs_differ"]
    assert cross["witnesses_must_not_be_spliced"]
    assert not cross["generic_mercury_association_adjudicated"]


@pytest.mark.parametrize(
    "body,x,expected",
    [
        ("Sun", 75, 30),
        ("Sun", 285, Fraction("7.5")),
        ("Mars", 105, Fraction("52.5")),
        ("Jupiter", 135, 45),
        ("Saturn", 75, 75),
    ],
)
def test_independent_interpolated_clauses_on_given_strict_interiors(body, x, expected):
    assert value_from_clauses(body, Fraction(x), PRIMARY) == expected


@pytest.mark.parametrize("body,x", [("Mars", 90), ("Jupiter", 120), ("Saturn", 300)])
def test_audit_does_not_sneak_in_an_unadjudicated_special_endpoint(body, x):
    with pytest.raises(ValueError, match="endpoints"):
        value_from_clauses(body, Fraction(x), PRIMARY)


@pytest.mark.parametrize(
    "fault",
    ["transpose", "missing_blank", "missing_heading", "bad_minute", "unknown_sign"],
)
def test_reference_structure_and_coverage_cannot_be_relaxed(fault):
    d = copy.deepcopy(PRIMARY)
    if fault == "transpose":
        d["planet_order"].reverse()
    elif fault == "missing_blank":
        d["example53_angles_target_rows"][0].pop()
    elif fault == "missing_heading":
        d["example53_headers_degrees_minutes"].pop()
    elif fault == "bad_minute":
        d["example53_headers_degrees_minutes"][0][1] = 60
    else:
        d["nature_witness"]["signed_example_columns"]["Mercury"] = "unresolved"
    with pytest.raises(ValueError):
        build_report(d, LATER)


def test_native49scalars49signed_contributions_and7given_nature_sums():
    d = compare_native(PRIMARY)
    assert len(d["scalar_relations"]) == len(d["contribution_relations"]) == 49
    assert len(d["sum_relations"]) == 7
    assert d["scalar_exact_float_conflicts"] == []
    assert d["contribution_exact_float_conflicts"] == []
    assert d["sum_roundoff_conflicts"] == []
    assert d["given_natures_match"]
    assert not d["arbitrary_mercury_nature_selected"]


@pytest.mark.parametrize(
    "fault", ["scalar", "signed_contribution", "sum", "given_nature"]
)
def test_native_comparison_detects_corrupted_calculation_or_explanation(
    monkeypatch, fault
):
    from fatebridge.core import jyotish_balas

    original = jyotish_balas.aspect_strength

    def altered(longitudes):
        body = original(longitudes)
        branch = body["scenarios"]["moon_benefic__mercury_benefic"]
        if fault == "scalar":
            body["matrix"]["Mars"]["Saturn"] += 1
        elif fault == "signed_contribution":
            branch["contributions"]["Saturn"]["Mars"] += 1
        elif fault == "sum":
            branch["summary"]["Saturn"] += 1
        else:
            branch["natures"]["Mercury"] = "malefic"
        return body

    monkeypatch.setattr(jyotish_balas, "aspect_strength", altered)
    report = compare_native(PRIMARY)
    if fault == "given_nature":
        assert not report["given_natures_match"]
    else:
        assert report[
            {
                "scalar": "scalar_exact_float_conflicts",
                "signed_contribution": "contribution_exact_float_conflicts",
                "sum": "sum_roundoff_conflicts",
            }[fault]
        ]


def test_standalone_source_gate_and_exclusive_output_never_overwrite(tmp_path):
    command = [
        sys.executable,
        "-I",
        str(ROOT / "scripts/audit_jyotish_drik_editions.py"),
        "--report",
    ]
    output = tmp_path / "source.json"
    completed = subprocess.run([*command, str(output)], capture_output=True)
    assert completed.returncode == 1, completed.stderr
    assert json.loads(output.read_text())["literal_angle_cells"] == 29
    for target in [output, FIXTURE, ROOT / "tests/fixtures/jyotish-drik-primary.json"]:
        raw = target.read_bytes()
        rejected = subprocess.run([*command, str(target)], capture_output=True)
        assert rejected.returncode == 2
        assert target.read_bytes() == raw
