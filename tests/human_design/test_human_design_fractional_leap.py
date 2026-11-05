"""All original27 leap dates preserve accepted fractional-offset input labels."""

import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURE = Path(__file__).parents[1] / "data/human_design/fractional_leap"
PLAN = json.loads((FIXTURE / "plan.json").read_text())
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize(
    "case,fact",
    list(zip(PLAN["cases"], REFERENCE["cases"], strict=True)),
    ids=[r["id"] for r in PLAN["cases"]],
)
def test_every_original_input_keeps_label_sofa_axis_and_complete_reading(case, fact):
    assert case["id"] == fact["id"]
    value = execute_tool(SPEC, SPEC.request_model(**case["input"]))
    assert "error" not in value, value
    assert value["birth_utc"] == fact["utc_label"] == case["expected_utc_label"]
    clock = value["birth_clock_evidence"]
    assert clock["utc_label"] == value["birth_utc"]
    assert clock["following_utc_midnight"].endswith("T00:00:00+00:00")
    time = value["time_scales"]["personality"]
    assert (
        time["utc_is_leap_second"] is True
        and time["utc_label_status"] == "inserted_UTC_leap_second"
    )
    assert value["design_solver"]["civil_elapsed_days"] is None
    error = (
        abs(
            Fraction(time["jd_tt"])
            - Fraction(fact["tt_jd1"])
            - Fraction(fact["tt_jd2"])
        )
        * 86400
    )
    assert error <= Fraction(1, 5000)
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.mark.parametrize("offset", ["-0.0000000025", "-0.0002777775"])
def test_accepted_birth_interval_keeps_exact_nominal_leap_input_and_all_witnesses(
    offset,
):
    case = next(
        c
        for c in PLAN["cases"]
        if c["id"].startswith("2016-12-31") and c["input"]["birth_timezone"] == offset
    )
    value = execute_tool(
        SPEC, SPEC.request_model(**case["input"], birth_time_uncertainty_minutes=1)
    )
    assert value["birth_utc"] == case["expected_utc_label"]
    check = verify_human_design_reading(value)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_interval_evaluation_count"] > 0


@pytest.fixture(scope="module")
def last_microsecond_run():
    return execute_tool(SPEC, SPEC.request_model(**PLAN["cases"][-1]["input"]))


@pytest.mark.parametrize(
    "fault", ["midnight_label", "float_inverse_label", "leap_flag", "midnight_source"]
)
def test_fresh_hash_does_not_hide_input_display_alias_or_calendar_changes(
    last_microsecond_run, fault
):
    value = copy.deepcopy(last_microsecond_run)
    if fault == "midnight_label":
        value["birth_utc"] = "2017-01-01T00:00:00+00:00"
    elif fault == "float_inverse_label":
        tt = value["time_scales"]["personality"]["jd_tt"]
        events = value["clock_evidence"]["conversions"]
        native_label = next(
            e["utc_label"]
            for e in events
            if e["kind"] == "tt_to_utc_display" and e["jd_tt"] == tt
        )
        assert native_label != value["birth_utc"]
        value["birth_utc"] = native_label
    elif fault == "leap_flag":
        value["time_scales"]["personality"]["utc_is_leap_second"] = False
    else:
        value["birth_clock_evidence"][
            "following_utc_midnight"
        ] = "2017-01-01T00:00:00.999999+00:00"
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"
