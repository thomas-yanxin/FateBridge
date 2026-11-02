"""Independent angle checks, exact source-role corruption and native qualifiers."""

import copy
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.day_meridian import (
    build_day_meridian,
    day_meridian_coordinates,
)
from fatebridge.core.output_midpoints import MidpointAnalysis
from fatebridge.services.astrology import calculate_germany_chart_analysis
from fatebridge.utils.errors import EphemerisSourceError

MANUAL = json.loads(
    (Path(__file__).parent / "fixtures/day-meridian-qualification.json").read_text()
)
BIRTH = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
PAYLOAD = dict(
    name="虚构：日推运资格核验",
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=10,
    birth_latitude=20,
    hsys=1,
)
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


def context(definition=None):
    # Toy Sun positions verify roles only, not real astronomical positions.
    analysis = BIRTH + timedelta(days=365.25)
    tt = 2451545.0
    observations = []
    indices = {}

    def observe(epoch, longitude):
        if epoch not in indices:
            indices[epoch] = len(observations)
            observations.append(
                dict(index=len(observations), julian_day_tt=epoch, longitude=longitude)
            )
        return indices[epoch]

    ni = observe(tt, 20.0)
    pi = observe(tt + 1, 25.0)
    target_index = observe(tt + 365.25, 40.0)
    profile = dict(
        birth_julian_day_tt=tt,
        birth_effective_utc=BIRTH.isoformat(),
        analysis_utc=analysis.isoformat(),
        year_days=365.25,
        key_years=1.0,
        progressed_julian_day_tt=tt + 1,
        natal_tropical_sun=20.0,
        progressed_tropical_sun=25.0,
        solar_arc_degrees=5.0,
        sun_observation_indices=[ni, pi],
        sun_ephemeris_source={"observations": observations},
        key_policy="Toy role fixture",
    )
    native_profile = {"julian_day_tt": tt}
    factor = {"id": "Midheaven", "longitude": 10.0}
    if definition:
        native_profile["angle_definition"] = copy.deepcopy(definition)
        if definition["status"] == "geographic_pole_meridian_convention":
            factor.update(
                coordinate_basis="geographic_pole_meridian_convention",
                angle_definition=copy.deepcopy(definition),
            )
    native = []
    derived = []
    for offset, mc in [(-30, 9.0), (0, 10.0), (30, 11.0)]:
        instant = BIRTH + timedelta(seconds=offset)
        epoch = tt + offset / 86400
        key = ((analysis - instant).total_seconds() / 86400) / 365.25
        progressed = epoch + key
        raw = dict(
            offset_seconds=float(offset),
            recorded_utc=instant.isoformat(),
            effective_utc=instant.isoformat(),
            julian_day_tt=epoch,
            factor_longitudes={"Midheaven": mc},
        )
        # Explicit toy arithmetic; frozen hand expectations and complex phases
        # below independently check the numerical method.
        row = dict(
            offset_seconds=float(offset),
            recorded_utc=instant.isoformat(),
            effective_utc=instant.isoformat(),
            julian_day_tt=epoch,
            progressed_julian_day_tt=progressed,
            key_years=key,
            sun_observation_indices=[observe(epoch, 20.0), observe(progressed, 25.0)],
            natal_upper_meridian_longitude=mc,
            natal_lower_meridian_longitude=mc + 180,
            natal_tropical_sun=20.0,
            target_tropical_sun=40.0,
            solar_arc_degrees=5.0,
            solar_arc_midheaven_longitude=mc + 5,
            transit_sun_displacement_degrees=20.0,
            upper_meridian_longitude=mc + 25,
            lower_meridian_longitude=mc + 205,
        )
        if definition:
            raw["angle_definition"] = copy.deepcopy(definition)
            row["angle_definition"] = copy.deepcopy(definition)
        native.append(raw)
        derived.append(row)
    uncertainty = dict(
        status="sampled",
        uncertainty_minutes=0.5,
        sample_count=3,
        samples=native,
        recorded_interval_start_utc=native[0]["recorded_utc"],
        recorded_interval_end_utc=native[-1]["recorded_utc"],
        represented_radius_seconds=30.0,
        maximum_recorded_sample_gap_seconds=30.0,
    )
    return dict(
        natal_upper_meridian=10.0,
        native_profile=native_profile,
        native_factors=[factor],
        nominal_effective_utc=BIRTH.isoformat(),
        supported_key_years=(0.0, 150.0),
        solar_profile=profile,
        target=dict(
            analysis_utc=analysis.isoformat(),
            target_julian_day_tt=tt + 365.25,
            target_tropical_sun=40.0,
            target_sun_observation_index=target_index,
        ),
        uncertainty=uncertainty,
        samples=derived,
    )


@pytest.mark.parametrize("row", MANUAL["rows"], ids=lambda r: r["id"])
def test_frozen_hand_arithmetic_and_independent_circle(row):
    result = day_meridian_coordinates(
        row["mc"], row["natal_sun"], row["arc"], row["target_sun"]
    )
    assert result["upper_meridian_longitude"] == row["expected_mc"]
    assert result["lower_meridian_longitude"] == row["expected_ic"]
    phase = math.radians(row["mc"] + row["arc"] - row["natal_sun"] + row["target_sun"])
    expected = math.degrees(math.atan2(math.sin(phase), math.cos(phase))) % 360
    assert result["upper_meridian_longitude"] == pytest.approx(
        expected, abs=1e-12, rel=0
    )


@pytest.mark.parametrize("value", [True, False, None, "0", float("nan"), float("inf")])
def test_invalid_source_numbers_cannot_become_angles(value):
    with pytest.raises(ValueError, match="finite"):
        day_meridian_coordinates(value, 20.0, 5.0, 40.0)


@pytest.mark.parametrize("mode", ["resolved", "asc_only_unresolved", "mc_unresolved"])
def test_exact_roles_and_reference_qualification_without_ephemeris_queries(
    mode, monkeypatch
):
    args = context(MANUAL["reference_cases"][mode])
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *_: pytest.fail("Derived qualification must not query ephemeris"),
    )
    result = build_day_meridian(**args)
    p = result["profile"]
    s = result["birth_time_sensitivity"]
    assert (
        result["input_coherence"]["status"] == "verified"
        and result["input_coherence"]["nominal_sample_index"] == 1
    )
    assert (
        p["natal_tropical_sun"],
        p["target_tropical_sun"],
        p["solar_arc_degrees"],
    ) == (20, 40, 5)
    if mode == "mc_unresolved":
        assert result["status"] == s["status"] == "partial"
        assert s["resolved_reference_sample_count"] == 0 and s[
            "unresolved_reference_sample_indices"
        ] == [0, 1, 2]
        assert p["upper_meridian_longitude"] is p["lower_meridian_longitude"] is None
        assert p["backend_convention"]["upper_meridian_longitude"] == 35
        assert all(
            r["upper_meridian_longitude"] is None and r["solar_arc_degrees"] == 5
            for r in s["samples"]
        )
        for span in s["factor_spans"].values():
            assert span["minimum_offset_from_nominal_degrees"] is None
            assert (
                span["backend_convention_span"]["minimum_offset_from_nominal_degrees"]
                == -1
            )
            assert (
                span["backend_convention_span"]["maximum_offset_from_nominal_degrees"]
                == 1
            )
    else:
        assert result["status"] == "computed" and s["status"] == "sampled"
        assert (
            p["upper_meridian_longitude"] == 35 and p["lower_meridian_longitude"] == 215
        )
        assert "backend_convention" not in p
    model = MidpointAnalysis.model_validate(
        {"solar_arc_analysis": {"daily_meridian": result}}
    )
    assert (
        model.model_dump(exclude_unset=True)["solar_arc_analysis"]["daily_meridian"]
        == result
    )


def test_known_absolute_samples_survive_an_unknown_nominal_reference():
    args = context(MANUAL["reference_cases"]["mc_unresolved"])
    for rows in [args["samples"], args["uncertainty"]["samples"]]:
        rows[0].pop("angle_definition")
    s = build_day_meridian(**args)["birth_time_sensitivity"]
    assert s["samples"][0]["upper_meridian_longitude"] == 34
    assert s["unresolved_reference_sample_indices"] == [1, 2]
    assert (
        s["factor_spans"]["upper_meridian_longitude"][
            "maximum_offset_from_nominal_degrees"
        ]
        is None
    )


def test_unknown_non_nominal_samples_have_separate_formal_bounds():
    args = context()
    for rows in [args["samples"], args["uncertainty"]["samples"]]:
        rows[0]["angle_definition"] = copy.deepcopy(
            MANUAL["reference_cases"]["mc_unresolved"]
        )
    s = build_day_meridian(**args)["birth_time_sensitivity"]
    span = s["factor_spans"]["upper_meridian_longitude"]
    assert span["status"] == "partial_reference_geometry"
    assert span["minimum_offset_from_nominal_degrees"] == 0
    assert span["backend_convention_span"]["minimum_offset_from_nominal_degrees"] == -1
    assert s["resolved_reference_sample_count"] == 2


def corrupt(a, case):
    if case == "native_tt":
        a["native_profile"]["julian_day_tt"] += 1
    elif case == "native_mc":
        a["native_factors"][0]["longitude"] += 1
    elif case == "bad_definition":
        a["native_profile"]["angle_definition"] = {"status": False}
    elif case == "missing_sample":
        a["samples"].pop()
    elif case == "reordered":
        a["uncertainty"]["samples"].reverse()
        a["samples"].reverse()
    elif case == "duplicate_offset":
        a["samples"][0]["offset_seconds"] = 0
        a["uncertainty"]["samples"][0]["offset_seconds"] = 0
    elif case == "sample_tt":
        a["samples"][0]["julian_day_tt"] += 1
    elif case == "sample_mc":
        a["samples"][0]["natal_upper_meridian_longitude"] += 1
    elif case == "sample_upper":
        a["samples"][1]["upper_meridian_longitude"] += 1
    elif case == "sample_lower":
        a["samples"][1]["lower_meridian_longitude"] += 1
    elif case == "sample_sun":
        a["samples"][1]["natal_tropical_sun"] += 1
    elif case == "target_stamp":
        a["target"]["analysis_utc"] = (
            datetime.fromisoformat(a["target"]["analysis_utc"]) + timedelta(seconds=1)
        ).isoformat()
    elif case == "target_index_bool":
        a["target"]["target_sun_observation_index"] = True
    elif case == "sample_observation":
        a["samples"][0]["sun_observation_indices"][1] = a["target"][
            "target_sun_observation_index"
        ]
    elif case == "sample_progressed_tt":
        a["samples"][0]["progressed_julian_day_tt"] += 1
    elif case == "nominal_key":
        a["solar_profile"]["key_years"] += 1
    elif case == "zero_native_mc":
        a["uncertainty"]["samples"][1]["factor_longitudes"]["Midheaven"] += 1
    elif case == "effective_clock":
        a["samples"][0]["effective_utc"] = (BIRTH - timedelta(seconds=29)).isoformat()
    elif case == "recorded_clock":
        a["samples"][0]["recorded_utc"] = (BIRTH - timedelta(seconds=29)).isoformat()
    elif case == "truncate_native_too":
        a["samples"].pop()
        a["uncertainty"]["samples"].pop()
        a["uncertainty"]["sample_count"] = 2
    elif case == "nominal_unavailable":
        a["samples"][1].update(status="unavailable", reason_code="fictional gap")
    elif case == "observation_sun":
        a["solar_profile"]["sun_ephemeris_source"]["observations"][0]["longitude"] += 1
    elif case == "wrong_basis":
        a["native_factors"][0][
            "coordinate_basis"
        ] = "geographic_pole_meridian_convention"
    elif case == "missing_epoch":
        a["samples"][0].pop("julian_day_tt")
    elif case == "unsupported_status":
        a["samples"][0]["status"] = "computed_maybe"
    elif case == "gap_metadata":
        a["uncertainty"]["maximum_recorded_sample_gap_seconds"] = 29
    elif case == "duplicate_observation_epoch":
        rows = a["solar_profile"]["sun_ephemeris_source"]["observations"]
        rows.append({**rows[0], "index": len(rows)})

    elif case == "same_instant_target_epoch":
        a["solar_profile"].update(
            analysis_utc=BIRTH.isoformat(),
            key_years=0.0,
            progressed_julian_day_tt=a["native_profile"]["julian_day_tt"],
            progressed_tropical_sun=20.0,
            solar_arc_degrees=0.0,
            sun_observation_indices=[0, 0],
        )
        a["target"]["analysis_utc"] = BIRTH.isoformat()
        a["uncertainty"] = {"status": "not_assessed", "uncertainty_minutes": None}
        a["samples"] = []
    else:
        raise AssertionError(case)


@pytest.mark.parametrize(
    "case",
    [
        "native_tt",
        "native_mc",
        "bad_definition",
        "missing_sample",
        "reordered",
        "duplicate_offset",
        "sample_tt",
        "sample_mc",
        "sample_upper",
        "sample_lower",
        "sample_sun",
        "target_stamp",
        "target_index_bool",
        "sample_observation",
        "sample_progressed_tt",
        "nominal_key",
        "zero_native_mc",
        "effective_clock",
        "recorded_clock",
        "truncate_native_too",
        "nominal_unavailable",
        "observation_sun",
        "wrong_basis",
        "missing_epoch",
        "unsupported_status",
        "gap_metadata",
        "duplicate_observation_epoch",
        "same_instant_target_epoch",
    ],
)
def test_incoherent_backend_sources_raise_runtime503(case):
    args = context()
    corrupt(args, case)
    with pytest.raises(EphemerisSourceError) as exc:
        build_day_meridian(**args)
    r = exc.value.as_result()
    assert r["status_code"] == 503 and r["retryable"] is False
    assert r["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "day_meridian_inputs"}
    ]


@HAS_SWE
@pytest.mark.parametrize("latitude", [-90, 90])
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("radius", [None, 0, 0.5])
def test_actual_poles_keep_only_mc_dependent_coordinates_unknown(
    latitude, zodiacal, radius
):
    result = calculate_germany_chart_analysis(
        **{**PAYLOAD, "birth_latitude": latitude},
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=radius,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    assert "error" not in result, result
    layer = result["midpoint_analysis"]
    day = layer["solar_arc_analysis"]["daily_meridian"]
    p = day["profile"]
    s = day["birth_time_sensitivity"]
    assert day["status"] == "partial" and day["input_coherence"]["status"] == "verified"
    for k in [
        "natal_upper_meridian_longitude",
        "natal_lower_meridian_longitude",
        "solar_arc_midheaven_longitude",
        "upper_meridian_longitude",
        "lower_meridian_longitude",
    ]:
        assert p[k] is None and p["backend_convention"][k] is not None
    assert (
        p["solar_arc_degrees"]
        == layer["solar_arc_analysis"]["profile"]["solar_arc_degrees"]
        and p["target_tropical_sun"] is not None
    )
    if radius is None:
        assert (
            s["status"] == "not_assessed"
            and "samples" not in s
            and day["input_coherence"]["sample_count"] is None
        )
    else:
        n = 1 if radius == 0 else 3
        assert (
            s["sample_count"] == s["unresolved_reference_sample_count"] == n
            and s["resolved_reference_sample_count"] == 0
        )
        assert all(
            r["upper_meridian_longitude"] is None
            and r["julian_day_tt"] is not None
            and len(r["sun_observation_indices"]) == 2
            for r in s["samples"]
        )


@HAS_SWE
@pytest.mark.parametrize("key_years", [0, 150])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_model_unavailability_and_unresolved_reference_remain_separate(
    key_years, zodiacal
):
    result = calculate_germany_chart_analysis(
        **{**PAYLOAD, "birth_latitude": 90},
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=1,
        analysis_datetime=BIRTH + timedelta(days=365.25 * key_years),
    )
    assert "error" not in result, result
    s = result["midpoint_analysis"]["solar_arc_analysis"]["daily_meridian"][
        "birth_time_sensitivity"
    ]
    assert (
        s["sample_count"] == 5
        and s["computed_sample_count"] == 3
        and s["unavailable_sample_count"] == 2
    )
    assert (
        s["unresolved_reference_sample_count"] == 3
        and s["resolved_reference_sample_count"] == 0
    )
    for r in s["samples"]:
        if r.get("status") == "unavailable":
            assert "backend_convention" not in r and "solar_arc_degrees" not in r
        else:
            assert (
                r["upper_meridian_longitude"] is None
                and r["backend_convention"]["upper_meridian_longitude"] is not None
            )


@HAS_SWE
@pytest.mark.parametrize("latitude", [-89.9, 89.9])
def test_nearby_resolved_poles_remain_computed(latitude):
    r = calculate_germany_chart_analysis(
        **{**PAYLOAD, "birth_latitude": latitude},
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    assert "error" not in r, r
    d = r["midpoint_analysis"]["solar_arc_analysis"]["daily_meridian"]
    assert (
        d["status"] == "computed"
        and d["profile"]["upper_meridian_longitude"] is not None
    )
    assert "backend_convention" not in d["profile"]


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_only_unresolved_asc_does_not_restrict_day_mc(zodiacal):
    r = calculate_germany_chart_analysis(
        **{
            **PAYLOAD,
            "birth_longitude": 169.5414439374805,
            "birth_latitude": -66.56232328397007,
        },
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=1,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    assert "error" not in r, r
    d = r["midpoint_analysis"]["solar_arc_analysis"]["daily_meridian"]
    assert d["profile"]["angle_definition"]["geometric_ascendant_resolved"] is False
    assert (
        d["status"] == "computed" and d["birth_time_sensitivity"]["status"] == "sampled"
    )


@HAS_SWE
def test_real_service_rejects_corrupt_derived_sample_as503(monkeypatch):
    import fatebridge.core.astro.solar_arc as module

    original = module.day_meridian_coordinates

    def wrong(*args):
        result = original(*args)
        result["upper_meridian_longitude"] = (
            result["upper_meridian_longitude"] + 1
        ) % 360
        return result

    monkeypatch.setattr(module, "day_meridian_coordinates", wrong)
    r = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    assert r["status_code"] == 503 and r["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "day_meridian_inputs"}
    ]


@HAS_SWE
def test_target_aligned_with_non_nominal_sample_reuses_its_true_tt_observation():
    r = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_time_uncertainty_minutes=0.5,
        analysis_datetime=BIRTH + timedelta(seconds=30),
    )
    assert "error" not in r, r
    d = r["midpoint_analysis"]["solar_arc_analysis"]["daily_meridian"]
    last = d["birth_time_sensitivity"]["samples"][-1]
    assert last["effective_utc"] == d["profile"]["analysis_utc"]
    assert last["julian_day_tt"] == d["profile"]["target_julian_day_tt"]
    assert (
        last["sun_observation_indices"]
        == [d["profile"]["target_sun_observation_index"]] * 2
    )
    assert d["input_coherence"]["status"] == "verified"
