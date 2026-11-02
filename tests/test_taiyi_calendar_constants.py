"""Frozen native readings, exact units and unresolved arithmetic stay separate."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction

import pytest

from fatebridge.validation.taiyi_calendar import audit_edition
from scripts.audit_taiyi_calendar_constants import CORPUS, audit, verify_sources

READINGS, EXPECTED = verify_sources()
CASES = [
    (edition, relation, status)
    for edition in READINGS["editions"]
    for relation, status in EXPECTED[edition].items()
]


@pytest.mark.parametrize("edition,relation,status", CASES)
def test_all_frozen_relations_including_differences_and_unknowns(
    edition, relation, status
):
    result = audit_edition(READINGS["editions"][edition]["readings"])
    rows = {r["id"]: r for r in result["relations"]}
    assert len(rows) == 8
    assert rows[relation]["status"] == status


def test_native_ming_chain_and_half_hour_units_are_exact_not_float_closeness():
    # Hand products recorded before the diagnostic implementation; no API chart
    # generated these expectations or selected a source value after comparison.
    assert 8126 * 1447 == 11_758_322
    assert 657 * 49 == 32_193
    assert 11_758_322 - 360 * 32_193 == 168_842
    assert Fraction(11_758_322, 32_193) / 2 == 182 + Fraction(20_035, 32_193)
    assert Fraction(32_193, 24) == 1341 + Fraction(9, 24)
    result = audit()
    assert result["counts"] == {"matching": 5, "different": 7, "unresolved": 4}
    assert result["software_preserves_frozen_diagnostic_expectations"]
    assert result["dated_cases"] == 0
    assert result["whole_calendar_acceptance"] is False


def test_unique_fraction_candidate_is_not_written_back_as_a_source_reading():
    original = READINGS["editions"]["ncl_ming"]["readings"]
    before = copy.deepcopy(original)
    result = audit_edition(original)
    row = next(r for r in result["relations"] if r["id"] == "double_hour_fraction")
    assert row["required_numerator_if_identity"] == {"numerator": 9, "denominator": 1}
    assert row["status"] == "unresolved"
    assert row["proper_fraction_can_satisfy"] is True
    assert row["literal_numerator_adjudicated"] is False
    assert original == before
    assert original["double_hour_fraction_numerator"]["value"] is None
    assert original["double_hour_fraction_numerator"]["literal"] == "之也"
    next_qi = next(r for r in result["relations"] if r["id"] == "next_qi_increment")
    assert next_qi["status"] == "unresolved"
    assert next_qi["inferred_compatible_candidate_not_source_value"]["adopted"] is False


@pytest.mark.parametrize("edition", ["siku", "ncl_ming"])
def test_literal_leap_step_fails_whole_chapter_for_every_allowed_start_remainder(
    edition,
):
    result = audit_edition(READINGS["editions"][edition]["readings"])
    row = next(r for r in result["relations"] if r["id"] == "literal_leap_step_cycle")
    expected = EXPECTED["expected_leap_cycle"][edition]
    assert row["required_leap_months"] == expected["required_leap_months"]
    assert row["possible_literal_carries"] == expected["possible_literal_carries"]
    assert row["required_leap_months"] not in row["possible_literal_carries"]
    assert row["status"] == "different"
    assert "完整置閏法" in row["scope"]


@pytest.mark.parametrize("change", ["image", "drop_edition", "move_expectation"])
def test_source_or_requirement_changes_fail_even_with_rewritten_local_hashes(
    tmp_path, change
):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    if change == "image":
        path = target / "ncl-native-page13.png"
        path.write_bytes(path.read_bytes() + b"changed")
    elif change == "drop_edition":
        path = target / "readings.json"
        data = json.loads(path.read_text())
        del data["editions"]["siku"]
        path.write_text(json.dumps(data))
    else:
        path = target / "expected-relations.json"
        data = json.loads(path.read_text())
        data["ncl_ming"]["double_hour_fraction"] = "matching"
        path.write_text(json.dumps(data))
    if change != "image":
        freeze = target / "initial-freeze.json"
        data = json.loads(freeze.read_text())
        data["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        freeze.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="freeze|fingerprint"):
        audit(target)


def test_regular_month_hypothesis_does_not_turn_matching_carry_count_into_closure():
    result = audit()
    for name, expected in (("ncl_ming", [242, 243]), ("siku", [241, 242])):
        row = next(
            r
            for r in result["editions"][name]["relations"]
            if r["id"] == "literal_leap_step_cycle"
        )
        other = row["post_freeze_regular_month_only_hypothesis_not_adopted"]
        assert other["possible_carries"] == expected
        assert other["exact_cycle_closure"] is False
        assert row["status"] == "different"
    ming = result["editions"]["ncl_ming"]["relations"][-1]
    hypothesis = ming["post_freeze_regular_month_only_hypothesis_not_adopted"]
    assert hypothesis["exact_residual_after_required_leaps"] == {
        "numerator": 657,
        "denominator": 25,
    }
    assert hypothesis["step_needed_for_exact_closure"] == {
        "numerator": 121,
        "denominator": 6,
    }
    assert result["counts"] == EXPECTED["expected_total"]


@pytest.mark.parametrize(
    "value", [True, 657.0, "657", {"numerator": 1, "denominator": 0}]
)
def test_source_values_are_exact_and_never_coerced(value):
    readings = copy.deepcopy(READINGS["editions"]["ncl_ming"]["readings"])
    readings["chapter_years"]["value"] = value
    with pytest.raises(ValueError):
        audit_edition(readings)


def test_audit_command_preserves_nonacceptance_and_all_requirements(tmp_path):
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/audit_taiyi_calendar_constants.py",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    result = json.loads(output.read_text())
    assert result["required_relations"] == 16
    assert result["counts"] == EXPECTED["expected_total"]
    assert result["whole_calendar_acceptance"] is False
