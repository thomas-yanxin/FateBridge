"""Frozen independent UTC/UT1/TT facts survive full charts and fixed readings."""

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURE = Path(__file__).parent / "data/human_design/decimal_offset"
PLAN = json.loads((FIXTURE / "plan.json").read_text())
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize(
    "case,fact",
    list(zip(PLAN["valid_cases"], REFERENCE["cases"])),
    ids=[r["id"] for r in PLAN["valid_cases"]],
)
def test_every_original_case_matches_the_frozen_sofa_axis_and_full_reading(case, fact):
    assert case["id"] == fact["id"]
    value = execute_tool(SPEC, SPEC.request_model(**case["input"]))
    assert "error" not in value, value
    assert datetime.fromisoformat(value["birth_utc"]) == datetime.fromisoformat(
        case["expected_utc_label"]
    )
    if fact["axis"] == "UTC_TAI_TT":
        expected = Fraction(fact["tt_jd1"]) + Fraction(fact["tt_jd2"])
        actual = value["time_scales"]["personality"]["jd_tt"]
    else:
        expected = Fraction(fact["jd_numerator"]) / Fraction(fact["jd_denominator"])
        actual = value["time_scales"]["personality"]["jd_ut1"]
    assert abs(Fraction(actual) - expected) * 86400 <= Fraction(1, 5000)
    if fact.get("future_warning"):
        assert (
            value["time_scales"]["personality"]["future_leap_seconds_assumed_unchanged"]
            is True
        )
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check
