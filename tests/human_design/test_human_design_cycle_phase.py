"""Independent analytic roots and direct natal-relative residuals, no drift."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_cycles import PHASE_METHOD, derive_body_contacts
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-cycle-phase-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
CASES = [
    (birth, natal, body)
    for birth in PLAN["birth_tt"]
    for natal in PLAN["natal_longitudes"]
    for body in PLAN["bodies"]
]
SPEC = next(s for s in CATALOG if s.key == "human_design")


def direct_residual(longitude, natal, target):
    # Direct oracle: no grid, no phase accumulator, no production angle helper.
    difference = (Fraction(longitude) - Fraction(natal)) % 360
    return difference - 180 if target == 180 else (difference + 180) % 360 - 180


@pytest.mark.parametrize("birth,natal,body", CASES)
def test_all_24_known_analytic_roots_remain_in_the_reported_bracket(birth, natal, body):
    rate = Fraction(body["target_arc"], body["target_offset_days"])
    original = Fraction(natal)
    origin = Fraction(birth)
    exact_root = origin + body["target_offset_days"]
    known = float(exact_root)
    assert Fraction(known) == exact_root

    def read(tt):
        return [
            tt,
            float((original + rate * (Fraction(tt) - origin)) % 360),
            float(rate),
            258,
        ]

    result = derive_body_contacts(body["body"], birth, read)
    assert result["status"] == "sampled_search_completed"
    assert len(result["contacts"]) == 1
    event = result["contacts"][0]
    lo, hi = event["bracket_jd_tt"]
    assert lo <= known <= hi
    assert hi - lo <= 0.0002 / 86400
    expected = direct_residual(event["longitude"], natal, body["target_arc"])
    assert event["residual_degrees"] == float(expected)
    assert (
        Fraction(
            int(event["exact_residual"]["numerator"]),
            int(event["exact_residual"]["denominator"]),
        )
        == expected
    )
    assert event["phase_arithmetic_method"] == PHASE_METHOD


@pytest.fixture(scope="module")
def complete():
    return execute_tool(
        SPEC,
        SPEC.request_model(
            birth_year=1980,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_minute=0,
            birth_timezone="UTC",
            cycle_reference_datetime="2029-07-01T00:00:00Z",
        ),
    )


def test_real_contacts_have_direct_source_bound_residuals_and_no_phase_assignment(
    complete,
):
    context = complete["cycle_context"]
    assert [len(row["contacts"]) for row in context["bodies"]] == [1, 3, 3]
    for row in context["bodies"]:
        assert row["phase_arithmetic_method"] == PHASE_METHOD
        for event in row["contacts"]:
            expected = direct_residual(
                event["longitude"], row["natal_longitude"], row["target_arc_degrees"]
            )
            assert event["residual_degrees"] == float(expected)
            assert (
                Fraction(
                    int(event["exact_residual"]["numerator"]),
                    int(event["exact_residual"]["denominator"]),
                )
                == expected
            )
    summary = complete["cycle_summary"]
    assert summary["phase_arithmetic_method"] == PHASE_METHOD
    assert "不提高原星历或出生钟精度" in summary["arithmetic_scope"]
    assert summary["sixth_line"]["current_phase"] is None
    assert summary["timing_accuracy_certified"] is False
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.mark.parametrize(
    "tamper",
    [
        "exact_residual",
        "reported_residual",
        "method",
        "body_method",
        "summary_method",
        "arithmetic_meaning",
    ],
)
def test_forged_residual_and_precision_claims_are_rejected_even_after_rehash(
    complete, tamper
):
    value = deepcopy(complete)
    row = value["cycle_context"]["bodies"][0]
    event = row["contacts"][0]
    if tamper == "exact_residual":
        event["exact_residual"]["numerator"] = "123"
    elif tamper == "reported_residual":
        event["residual_degrees"] = 1e-8
    elif tamper == "method":
        event["phase_arithmetic_method"] = "independent_sky_certificate"
    elif tamper == "body_method":
        row["phase_arithmetic_method"] = "rounded_accumulation"
    elif tamper == "summary_method":
        value["cycle_summary"]["phase_arithmetic_method"] = "full_precision"
    else:
        value["cycle_summary"]["arithmetic_scope"] = "数值根已认证出生钟和物理精度。"
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"
