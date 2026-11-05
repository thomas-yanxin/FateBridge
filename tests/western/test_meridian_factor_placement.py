"""Full ecliptic directions, exact sector boundaries and actual sampled factors."""

import json
import math
import subprocess
import sys

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.meridian_placement import (
    attach_factor_placement,
    factor_position,
    house_from_ra,
    placement_sample_summaries,
)
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES, _native_factors
from fatebridge.core.output_midpoints import MeridianFactorPlacement
from fatebridge.services.astrology import calculate_germany_chart_analysis
from scripts.western import audit_meridian_factor_placement as oracle

HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
def test_registered_rodrigues_and_native_backend_matrix_retains_boundary_status():
    p = oracle.pinned(oracle.PROTOCOL, oracle.PROTOCOL_SHA256)
    result = oracle.grid(p)
    assert result["unique_direction_and_armc_configurations"] == 4320
    assert result["backend_comparisons"] == 21600
    assert result["numeric_checks_matched"]
    assert result["interior_integer_checks_matched"]
    assert result["integer_boundary_comparisons_unresolved"] > 0
    assert result["latitude_changes_house_unique_configurations"] > 0
    assert result["independent_sky_observations"] == 0
    assert result["physical_or_clock_error_bound"] is False


def test_every_exact_ra_cusp_and_its_nextafter_neighbors_preserve_half_open_policy():
    for house in range(1, 13):
        cusp = float(((house - 10) * 30) % 360)
        assert house_from_ra(cusp, 0.0)["house"] == house
        below = house_from_ra(math.nextafter(cusp, -math.inf), 0.0)
        above = house_from_ra(math.nextafter(cusp, math.inf), 0.0)
        assert below["house"] == (house - 2) % 12 + 1
        assert above["house"] == house
        assert below["house"] <= below["house_position"] < below["house"] + 1
        assert above["house"] <= above["house_position"] < above["house"] + 1


def test_zero_obliquity_preserves_exact_input_angle_instead_of_a_trig_roundtrip():
    for cusp in range(0, 360, 30):
        for longitude in [
            math.nextafter(float(cusp), -math.inf),
            float(cusp),
            math.nextafter(float(cusp), math.inf),
        ]:
            for latitude in [-60.0, -5.0, 0.0, 5.0, 60.0]:
                result = factor_position(
                    longitude=longitude, latitude=latitude, obliquity=0.0, armc=0.0
                )
                house, position, _ = oracle.reference_house(longitude, 0.0)
                assert result["status"] == "computed" and result["house"] == house
                assert result["declination"] == latitude
                assert result["right_ascension_raw_degrees"] == longitude
                assert (
                    abs(oracle.signed(result["house_position"], position, 12)) < 1e-12
                )


@pytest.mark.parametrize("eps", [0.0, 23.439291111, 45.0])
@pytest.mark.parametrize("sign", [-1, 1])
def test_equatorial_poles_keep_undefined_ra_and_house(eps, sign):
    r = factor_position(
        longitude=90.0 if sign == 1 else 270.0,
        latitude=sign * (90 - eps),
        obliquity=eps,
        armc=10.0,
    )
    assert r["status"] == "underdetermined_equatorial_pole"
    assert r["house"] is r["right_ascension"] is r["house_position"] is None
    assert r["latitude_changes_house"] is None
    assert abs(r["declination"]) == pytest.approx(90.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "5"])
def test_invalid_direction_axes_are_not_zero_or_accepted_as_exact(bad):
    with pytest.raises(ValueError):
        factor_position(longitude=0.0, latitude=bad, obliquity=23.0, armc=0.0)
    with pytest.raises(ValueError):
        house_from_ra(bad, 0.0)


@pytest.mark.parametrize("lat", [-90.1, 90.1])
def test_outside_ecliptic_latitude_is_rejected(lat):
    with pytest.raises(ValueError):
        factor_position(longitude=0.0, latitude=lat, obliquity=23.0, armc=0.0)


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("uncertainty", [None, 0, 1])
def test_real_nominal_and_every_sample_retain_same_run_latitude_and_house(
    zodiacal, uncertainty
):
    result = calculate_germany_chart_analysis(
        name="虚构：子午宫天体投影验收",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=uncertainty,
    )
    layer = result["midpoint_analysis"]
    m = layer["meridian_houses"]
    p = m["factor_placement"]
    MeridianFactorPlacement.model_validate(p)
    assert p["factor_count"] == len(p["factors"]) == 19
    assert len(layer["factors"]) == 22
    assert {x["id"] for x in p["factors"]} == set(PHYSICAL_BODIES) | {
        "North Node",
        "Cupido",
        "Hades",
        "Zeus",
        "Kronos",
        "Apollon",
        "Admetos",
        "Vulkanus",
        "Poseidon",
    }
    assert p["reference_points_included"] is False
    assert p["full_original_method_accepted"] is False
    assert p["real_world_efficacy"] == "not_tested"

    def verify(rows, armc, eps):
        for row in rows:
            ra, de = oracle.reference_rotation(
                row["input_tropical_longitude"], row["input_ecliptic_latitude"], eps
            )
            house, pos, _ = oracle.reference_house(ra, armc)
            assert row["status"] == "computed"
            assert abs(oracle.signed(row["right_ascension"], ra)) < 1e-10
            assert row["declination"] == pytest.approx(de, abs=1e-10)
            assert row["house"] == house
            assert abs(oracle.signed(row["house_position"], pos, 12)) < 1e-10

    verify(p["factors"], m["profile"]["armc"], m["profile"]["true_obliquity"])
    sensitivity = m["birth_time_sensitivity"]
    assert sensitivity["uncertainty_minutes"] == uncertainty
    if uncertainty is None:
        assert sensitivity["status"] == "not_assessed"
        assert "factor_placement_summary" not in sensitivity
        return
    samples = layer["time_sensitivity"]["samples"]
    assert len(samples) == (1 if uncertainty == 0 else 5)
    for sample in samples:
        verify(
            sample["meridian_factor_positions"],
            sample["meridian_armc"],
            sample["meridian_obliquity"],
        )
    for summary in sensitivity["factor_placement_summary"]:
        rows = [
            next(r for r in s["meridian_factor_positions"] if r["id"] == summary["id"])
            for s in samples
        ]
        assert summary["sampled_houses"] == sorted({r["house"] for r in rows})
        assert summary["unresolved_sample_count"] == 0
        assert summary["sampled_status"] in [
            "all_sampled_same_house_as_nominal",
            "varies_across_samples",
        ]
    assert sensitivity["continuous_interval_proven"] is False
    assert sensitivity["sample_frequency_is_probability"] is False


@HAS_SWE
@pytest.mark.parametrize("latitude", [float("nan"), None, True, "5", 91.0])
def test_missing_native_latitude_is_an_internal_failure_and_is_not_filled_with_zero(
    monkeypatch,
    latitude,
):
    original = runtime.ephemeris_call

    def broken(name, *args, **kwargs):
        result = original(name, *args, **kwargs)
        if name == "calc" and args[1] == runtime.swe.MOON:
            coords, flag = result
            coords = list(coords)
            coords[1] = latitude
            return coords, flag
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", broken)
    birth = build_astro_birth_info(
        name="虚构",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    with pytest.raises(RuntimeError, match="ecliptic latitude"):
        _native_factors(birth, False, include_meridian_houses=True)


@HAS_SWE
def test_same_physical_factors_restore_their_own_epoch_not_the_house_epoch():
    birth = build_astro_birth_info(
        name="虚构",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    trop = _native_factors(birth, False, include_meridian_houses=True)
    sid = _native_factors(birth, True, include_meridian_houses=True)
    for a, b in zip(
        trop["meridian_houses"]["factor_placement"]["factors"],
        sid["meridian_houses"]["factor_placement"]["factors"],
        strict=True,
    ):
        assert a["id"] == b["id"] and a["house"] == b["house"]
        assert (
            abs(
                oracle.signed(
                    a["input_tropical_longitude"], b["input_tropical_longitude"]
                )
            )
            < 1e-10
        )
        assert a["input_ecliptic_latitude"] == pytest.approx(
            b["input_ecliptic_latitude"], abs=1e-10
        )
        assert abs(oracle.signed(a["right_ascension"], b["right_ascension"])) < 1e-8


def test_undefined_sample_is_retained_and_missing_factors_are_rejected():
    m = {
        "factor_placement": {"factors": [{"id": "X", "house": 1, "status": "computed"}]}
    }
    s = {
        "status": "sampled",
        "samples": [
            {
                "meridian_factor_positions": [
                    {
                        "id": "X",
                        "status": "underdetermined_equatorial_pole",
                        "house": None,
                    }
                ]
            }
        ],
    }
    summary = placement_sample_summaries(m, s)[0]
    assert (
        summary["unresolved_sample_count"] == 1
        and summary["sampled_houses"] == []
        and summary["sampled_status"] == "underdetermined"
    )
    s["samples"][0]["meridian_factor_positions"] = []
    with pytest.raises(RuntimeError):
        placement_sample_summaries(m, s)


@HAS_SWE
def test_raw_printed_comparison_is_checked_without_a_birth_clock_or_fitted_obliquity():
    record = oracle.pinned(oracle.RECORD, oracle.RECORD_SHA256)
    result = oracle.source_cusps(record)
    assert result["printed_rows"] == 6
    assert len(result["columns"]) == 2
    assert result["historical_birth_clock_adopted"] is False
    assert result["full_original_method_accepted"] is False
    assert result["empirical_outcomes"] == 0
    assert all(len(c["rows"]) == 6 for c in result["columns"])
    for column in result["columns"]:
        assert column["all_six_meridian_intervals_overlap"] is False
        assert {
            r["house"]
            for r in column["rows"]
            if not r["source_and_mc_rounding_intervals_overlap"]
        } == {11, 12, 2}


@HAS_SWE
def test_geometry_pass_does_not_turn_unreconciled_source_example_into_exit_zero(
    tmp_path,
):
    target = tmp_path / "audit.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(oracle.ROOT / "scripts/western/audit_meridian_factor_placement.py"),
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1, completed.stderr
    report = json.loads(target.read_text())
    assert report["geometry"]["numeric_checks_matched"] is True
    assert report["source_table_reconciled_with_all_predeclared_models"] is False
    assert report["all_four_objectives_validated"] is False


@HAS_SWE
def test_actual_physical_only_probe_reports_its_eleven_factors_without_invented_hypotheticals():
    birth = build_astro_birth_info(
        name="虚构",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    p = _native_factors(
        birth, False, include_hypothetical=False, include_meridian_houses=True
    )["meridian_houses"]["factor_placement"]
    assert (
        p["factor_count"],
        p["physical_factor_count"],
        p["hypothetical_factor_count"],
        p["node_factor_count"],
    ) == (11, 10, 0, 1)


def test_empty_or_duplicate_placement_input_is_an_internal_failure():
    for rows in [[], [{"id": "Sun"}, {"id": "Sun"}]]:
        with pytest.raises(RuntimeError):
            attach_factor_placement({"profile": {}}, rows, factor_ayanamsha=0.0)
