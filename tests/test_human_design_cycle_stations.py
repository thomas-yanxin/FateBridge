"""Frozen station misses, independent roots, quantization limits and replays."""

import json
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.astro import native_execution, runtime
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-cycle-station-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def oracle(case):
    birth, centre = Fraction(case["birth_tt"]), Fraction(case["station_tt"])
    radius = Fraction(math.ulp(case["station_tt"])) * case["radius_ulps"]
    height = radius * radius / 10
    natal = Fraction(*PLAN["natal_longitude_rational"])

    def read(tt):
        x = Fraction(tt) - birth
        if x < 8:
            phase, speed = Fraction(35991, 100) * x / 8, Fraction(35991, 800)
        else:
            dx = Fraction(tt) - centre
            phase, speed = 360 + height - dx * dx / 10, -dx / 5
        return [tt, float((natal + phase) % 360), float(speed), 258]

    return read


def assert_adjacent_or_zero(lo, hi):
    assert lo == hi or math.nextafter(lo, math.inf) == hi


def test_original_24_failures_and_exact_acceptance_bars_stay_frozen():
    assert len(PLAN["cases"]) == 24
    assert sum(c["native_peak_distinguishable"] for c in PLAN["cases"]) == 12
    assert (
        cycles.ROOT_SECONDS
        == PLAN["unchanged_thresholds"]["cycle_contact_seconds"]
        == 0.0002
    )
    assert (
        cycles.STATION_SECONDS
        == PLAN["unchanged_thresholds"]["cycle_station_seconds"]
        == 0.01
    )
    assert cycles.RESIDUAL_DEGREES == 1e-7


@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_every_original_oracle_preserves_the_distinguishable_roots_and_unresolved_controls(
    case, monkeypatch
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", PLAN["horizon_days"])
    read = oracle(case)
    # This source-independent oracle still has TWO mathematical roots in every
    # original case, including the12returned-longitude quantization controls.
    natal = read(case["birth_tt"])[1]
    for tt in case["analytic_roots"]:
        assert read(tt)[1] == natal
    distinguishable = read(case["station_tt"])[1] > natal
    assert distinguishable == case["native_peak_distinguishable"]
    result = cycles.derive_body_contacts("Saturn", case["birth_tt"], read)
    assert result["status"] == "sampled_search_completed"
    assert result["observed_station_count"] == 1
    station = result["station_witnesses"][0]
    assert_adjacent_or_zero(*station["bracket_jd_tt"])
    assert station["jd_tt"] == case["station_tt"]
    assert station["longitude_speed"] == 0
    assert station["continuous_contact_multiplicity_certified"] is False
    assert result["root_method"] == cycles.ROOT_METHOD
    assert result["station_method"] == cycles.STATION_METHOD
    if distinguishable:
        assert len(result["contacts"]) == 2
        assert [e["motion"] for e in result["contacts"]] == ["direct", "retrograde"]
        for known, event in zip(
            case["analytic_roots"], result["contacts"], strict=True
        ):
            lo, hi = event["bracket_jd_tt"]
            assert lo <= known <= hi
            assert_adjacent_or_zero(lo, hi)
            assert event["bracket_width_seconds"] <= cycles.ROOT_SECONDS
            assert event["exact_residual"]["numerator"] == "0"
    else:
        # A single observed rounded zero is NOT counted as successful recovery
        # of the two analytic roots. These12cases remain unresolved in reports.
        assert len(result["contacts"]) == 1
        assert result["contacts"][0]["jd_tt"] == case["station_tt"]
        assert station["target_phase_exact_residual"]["numerator"] == "0"
        assert "不认证连续根数量" in result["numerical_scope"]


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
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


def forbidden(*args, **kwargs):
    raise AssertionError("Pure cycle verification called a native producer")


def test_real_all_cycle_brackets_and_selected_residuals_are_adjacent_or_zero(
    complete, monkeypatch
):
    assert [len(r["contacts"]) for r in complete["cycle_context"]["bodies"]] == [
        1,
        3,
        3,
    ]
    for row in complete["cycle_context"]["bodies"]:
        assert row["root_method"] == cycles.ROOT_METHOD
        assert row["station_method"] == cycles.STATION_METHOD
        for station in row["station_witnesses"]:
            assert_adjacent_or_zero(*station["bracket_jd_tt"])
            assert station["bracket_width_seconds"] <= cycles.STATION_SECONDS
            assert station["continuous_contact_multiplicity_certified"] is False
        for e in row["contacts"]:
            assert_adjacent_or_zero(*e["bracket_jd_tt"])
            lo, hi = [
                Fraction(r["numerator"]) / Fraction(r["denominator"])
                for r in e["bracket_exact_residuals"]
            ]
            selected = min(
                zip(e["bracket_jd_tt"], (lo, hi)), key=lambda x: (abs(x[1]), x[0])
            )
            assert e["jd_tt"] == selected[0]
            assert (
                Fraction(e["exact_residual"]["numerator"])
                / Fraction(e["exact_residual"]["denominator"])
                == selected[1]
            )
    assert complete["cycle_summary"]["root_method"] == cycles.ROOT_METHOD
    assert complete["cycle_summary"]["timing_accuracy_certified"] is False
    assert complete["cycle_summary"]["sixth_line"]["current_phase"] is None
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    result = verify_human_design_reading(complete)
    assert result["status"] == "verified_fixed_template_reading", result


@pytest.mark.parametrize("bad", PLAN["negative_receipts"])
def test_preregistered_station_and_contact_forgeries_rejected_after_rehash(
    complete, bad, monkeypatch
):
    run = deepcopy(complete)
    body = run["cycle_context"]["bodies"][0]
    station = body["station_witnesses"][0]
    event = body["contacts"][0]
    if bad == "station_epoch":
        station["jd_tt"] += 0.001
    elif bad == "station_bracket":
        station["bracket_jd_tt"][0] -= 0.001
    elif bad == "station_speed":
        station["bracket_longitude_speeds"][0] = 0.0
    elif bad == "station_phase":
        station["target_phase_exact_residual"]["numerator"] = "0"
    elif bad == "station_multiplicity":
        station["continuous_contact_multiplicity_certified"] = True
    elif bad == "contact_root_method":
        event["root_method"] = "exact_sky"
    elif bad == "contact_bracket_exact_residual":
        event["bracket_exact_residuals"][0]["numerator"] = "123"
    elif bad == "contact_root_selection":
        event["jd_tt"] = math.nextafter(event["jd_tt"], math.inf)
    elif bad == "summary_root_method":
        run["cycle_summary"]["root_method"] = "first_birth_return"
    elif bad == "summary_scope":
        run["cycle_summary"]["numerical_scope"] = "物理误差为零"
    elif bad == "missing_station_witness":
        body["station_witnesses"].pop()
    elif bad == "removed_retrograde_contact":
        run["cycle_context"]["bodies"][1]["contacts"].pop(1)
    else:
        raise AssertionError(bad)
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(run)["status"] == "rejected"


def test_distinct_nonzero_crossings_can_share_a_station_bracket_endpoint(monkeypatch):
    # Preregistered nonzero shared-endpoint requirement: two opposite sign
    # crossings occupy adjacent TT cells and share a positive station value.
    # Their true quadratic zeros lie between representable instants.
    monkeypatch.setattr(cycles, "HORIZON_DAYS", PLAN["horizon_days"])
    birth = 2451545.0
    centre = float(birth + 9 + 0.003 / 86400)
    radius = Fraction(math.ulp(centre))
    height = Fraction(3, 4) * radius * radius / 10
    natal = Fraction(*PLAN["natal_longitude_rational"])

    def read(tt):
        x = Fraction(tt) - Fraction(birth)
        if x < 8:
            phase, speed = Fraction(35991, 100) * x / 8, Fraction(35991, 800)
        else:
            dx = Fraction(tt) - Fraction(centre)
            phase, speed = 360 + height - dx * dx / 10, -dx / 5
        return [tt, float((natal + phase) % 360), float(speed), 258]

    assert read(centre)[1] > read(birth)[1]
    assert read(math.nextafter(centre, -math.inf))[1] < read(birth)[1]
    assert read(math.nextafter(centre, math.inf))[1] < read(birth)[1]
    result = cycles.derive_body_contacts("Saturn", birth, read)
    assert len(result["contacts"]) == 2
    left, right = result["contacts"]
    assert left["bracket_jd_tt"][1] == right["bracket_jd_tt"][0] == centre
    assert left["residual_degrees"] != 0 and right["residual_degrees"] != 0
    assert [left["motion"], right["motion"]] == ["direct", "retrograde"]
