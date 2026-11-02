"""Frozen clock contradictions must fail even after a fresh business hash."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_sample_witness import unpack_sample_witnesses
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_clocks import verify_clock_records

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
BEFORE = json.loads(
    (ROOT / "docs/validation/human-design-ordinary-clock-before.json").read_text()
)


def rehash(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    return value


def set_path(value, path, replacement):
    parts = path.split(".")
    target = value
    for key in parts[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    key = int(parts[-1]) if isinstance(target, list) else parts[-1]
    assert target[key] != replacement
    target[key] = replacement


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(
            SPEC,
            SPEC.request_model(**BEFORE["input"], birth_time_uncertainty_minutes=1),
        )


def test_original_cases_and_preregistered_acceptance_plan_stay_frozen():
    for path, sha in {
        "docs/validation/human-design-ordinary-clock-before.json": "5986043da4618391e9d6057f449068ea83ae39c6b07e0d50d7b6fdf18b8cf1a9",
        "docs/validation/human-design-interval-clock-before.json": "00fbc97db70a33ee114f0e9e7a669cd9c04a96aa164b4e3690c6bc98a6ebbec4",
        "tests/fixtures/human-design-clock-replay-plan.json": "0e37c8c1e0f02cb82b58ca9db3984bc0d677b595620a34cf7d970cb925e921ea",
    }.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
    assert len(BEFORE["mutations"]) == 9


@pytest.mark.parametrize("case", BEFORE["mutations"], ids=lambda c: c["id"])
def test_all_nine_original_rehashed_ordinary_clock_probes(complete, case):
    value = deepcopy(complete)
    set_path(value, case["path"], case["replacement"])
    assert verify_human_design_reading(rehash(value))["status"] == "rejected"


def test_original_nonnominal_UT1_failure_with_entire_interval_rebuilt(complete):
    before = json.loads(
        (ROOT / "docs/validation/human-design-interval-clock-before.json").read_text()
    )
    value = deepcopy(complete)
    set_path(value, before["mutation"]["path"], before["mutation"]["replacement"])
    raw = unpack_sample_witnesses(
        value["time_sensitivity"]["evaluation_witnesses"],
        value["calculation_policy"]["node_mode"],
        require_swiss_files=False,
        physical_backend_policy=value["calculation_policy"]["physical_backend_policy"],
    )
    value["time_sensitivity"] = assess_birth_interval(
        value,
        1,
        value["calculation_policy"]["node_mode"],
        _chart_reader=raw.__getitem__,
    )
    assert value["time_scales"] == complete["time_scales"]
    assert value["activations"] == complete["activations"]
    assert verify_human_design_reading(rehash(value))["status"] == "rejected"


MUTATIONS = [
    "design_UT1",
    "design_method",
    "design_future_assumption",
    "backend_reference_personality_UT1",
    "backend_reference_design_UT1",
    "missing_clock_evidence",
    "changed_clock_input",
    "changed_timezone_rule_identity",
    "changed_native_delta_T_step",
    "changed_native_delta_T_flag",
    "changed_native_delta_T_output",
    "invented_clock_authentication",
]


def mutate(value, case):
    if case.startswith("backend_reference_"):
        side = "personality" if "personality" in case else "design"
        value["ephemeris_backend_comparison"]["reference_chart"]["time_scales"][side][
            "jd_ut1"
        ] += 0.1
    elif case == "design_UT1":
        value["time_scales"]["design"]["jd_ut1"] += 0.1
    elif case == "design_method":
        value["time_scales"]["design"]["method"] = "calendar_accuracy_authenticated"
    elif case == "design_future_assumption":
        value["time_scales"]["design"]["future_leap_seconds_assumed_unchanged"] = True
    elif case == "missing_clock_evidence":
        del value["clock_evidence"]
    elif case == "changed_clock_input":
        value["clock_evidence"]["input"]["birth_hour"] += 1
    elif case == "changed_timezone_rule_identity":
        value["clock_evidence"]["timezone_rules"]["database"] = "unverified"
    elif case.startswith("changed_native_delta_T_"):
        event = next(
            e
            for e in value["clock_evidence"]["conversions"]
            if e["kind"] == "tt_to_ut1"
        )
        if case.endswith("step"):
            event["steps"][0][2] += 0.001
        elif case.endswith("flag"):
            event["steps"][0][1] = -1
        else:
            event["jd_ut1"] += 0.1
    elif case == "invented_clock_authentication":
        value["clock_evidence"]["native_execution_authenticated"] = True
    else:
        raise AssertionError(case)


@pytest.mark.parametrize("case", MUTATIONS)
def test_design_reference_and_observation_contradictions(complete, case):
    value = deepcopy(complete)
    mutate(value, case)
    assert verify_human_design_reading(rehash(value))["status"] == "rejected", case


def test_complete_interval_replay_uses_no_native_or_private_worker_calls(
    complete, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Reading replay called the native producer")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    for name in ("deltat_ex", "utc_to_jd", "jdet_to_utc", "calc", "calc_ut"):
        monkeypatch.setattr(runtime.swe, name, forbidden)
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_interval_evaluation_count"] == len(
        complete["time_sensitivity"]["evaluation_witnesses"]["samples"]
    )


@pytest.mark.parametrize(
    "year,second,zone",
    [
        (1800, 0, "UTC"),
        (1959, 0, "UTC"),
        (1960, 0, "UTC"),
        (1961, 0, "UTC"),
        (1971, 0, "UTC"),
        (1972, 0, "UTC"),
        (1990, 0, "UTC"),
        (2600, 0, "UTC"),
        (2016, 60, "UTC"),
        (1990, 0, "Asia/Shanghai"),
        (1990, 0, "+05:30"),
    ],
)
def test_declared_calendar_eras_and_explicit_timezone_controls(year, second, zone):
    args = dict(
        BEFORE["input"],
        birth_year=year,
        birth_month=12 if second else 1,
        birth_day=31 if second else 1,
        birth_hour=23 if second else 12,
        birth_minute=59 if second else 0,
        birth_second=second,
        birth_timezone=zone,
    )
    if year == 2600:
        # Keep the planned internal engine control; the public birth contract
        # still ends at2399. Do not widen that contract to make this test pass.
        with pytest.raises(ValidationError):
            SPEC.request_model(**args)
        result = calculate_human_design(**args)
        verify_clock_records(result)
        return
    result = execute_tool(SPEC, SPEC.request_model(**args))
    verify_clock_records(result)
    check = verify_human_design_reading(result)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.fixture(scope="module")
def cycle_run():
    return execute_tool(
        SPEC,
        SPEC.request_model(
            **BEFORE["input"], cycle_reference_datetime="2030-01-01T00:00:00Z"
        ),
    )


def test_cycle_replay_uses_no_native_or_private_worker_calls(cycle_run, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Cycle replay called the native producer")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    for name in ("deltat_ex", "utc_to_jd", "jdet_to_utc", "calc", "calc_ut"):
        monkeypatch.setattr(runtime.swe, name, forbidden)
    checked = verify_human_design_reading(cycle_run)
    assert checked["status"] == "verified_fixed_template_reading", checked
    assert checked["checked_cycle_evaluation_count"] > 35000


@pytest.mark.parametrize(
    "case",
    ["cycle_reference_UTC", "cycle_contact_UTC", "cycle_contact_future_assumption"],
)
def test_cycle_clock_contradictions_after_rehash(cycle_run, case):
    value = deepcopy(cycle_run)
    if case == "cycle_reference_UTC":
        value["cycle_context"]["reference_utc"] = "2031-01-01T00:00:00+00:00"
    else:
        event = next(
            r["contacts"][0] for r in value["cycle_context"]["bodies"] if r["contacts"]
        )
        if case == "cycle_contact_UTC":
            event["utc_label"] = "2031-01-01T00:00:00+00:00"
        else:
            event["future_leap_seconds_assumed_unchanged"] = not event[
                "future_leap_seconds_assumed_unchanged"
            ]
    assert verify_human_design_reading(rehash(value))["status"] == "rejected"
