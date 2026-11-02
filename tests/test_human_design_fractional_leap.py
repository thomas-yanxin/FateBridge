"""All original27 leap dates preserve accepted fractional-offset input labels."""

import copy
import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

FIXTURE = Path(__file__).parent / "fixtures/human_design_fractional_leap_v1"
PLAN = json.loads((FIXTURE / "plan.json").read_text())
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_independent_plan_oracle_and_original_wrong_receipt_remain_frozen():
    assert (
        hashlib.sha256((FIXTURE / "hashes.json").read_bytes()).hexdigest()
        == "989052e43afd52d0d42f9c60fd600ba87bae6c90bb5e1ce2474ee1ed11778881"
    )
    hashes = json.loads((FIXTURE / "hashes.json").read_text())
    for n, d in hashes.items():
        assert hashlib.sha256((FIXTURE / n).read_bytes()).hexdigest() == d
    assert (
        REFERENCE["plan_sha256"]
        == "827081e989d62e4436987dd47a3b9eccee5fa2672d7378acce278ddca8e4c819"
    )
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == "4449925d1714fde1a0be93c9edc356829c3f1ceece497e2e10ebc1a1cf363528"
    )
    assert PLAN["tolerance_seconds"] == 0.0002
    assert len(PLAN["cases"]) == len(REFERENCE["cases"]) == 135
    assert len({c["id"][:10] for c in PLAN["cases"]}) == 27


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


def test_original_accepted_nine_us_label_error_rejects_without_a_producer(monkeypatch):
    with gzip.open(FIXTURE / "before-9us-run.json.gz", "rt") as f:
        original = json.load(f)
    assert original["check"]["status"] == "verified_fixed_template_reading"
    assert original["result"]["birth_utc"] == "2016-12-31T23:59:60.000000+00:00"
    assert original["input"]["birth_timezone"] == "-0.0000000025"

    def forbidden(*a, **k):
        raise AssertionError("Stored receipt check invoked a native producer")

    monkeypatch.setattr(native_execution, "calculate", forbidden)
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    assert verify_human_design_reading(original["result"])["status"] == "rejected"


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
