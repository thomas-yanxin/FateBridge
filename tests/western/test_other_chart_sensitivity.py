"""Birth-time counterexamples and independent replay of sensitivity outputs."""

import math
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.sensitivity import time_sensitivity
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroSpecialtyRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from tests.fixtures.surface_payloads import astro_payload

STIMULUS = {
    "name": "虚构：生时误差接口反例",
    "birth_year": 2000,
    "birth_month": 1,
    "birth_day": 1,
    "birth_hour": 4,
    "birth_minute": 30,
    "birth_timezone": "UTC",
    "birth_longitude": 0.0,
    "birth_latitude": 0.0,
}
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


def test_unknown_uncertainty_does_not_get_imputed_as_zero(monkeypatch):
    birth = build_astro_birth_info(**STIMULUS)
    monkeypatch.setattr(
        "fatebridge.core.astro.sensitivity._native_factors",
        lambda *_: pytest.fail("Unknown interval must not generate pretend samples"),
    )
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=None)
    assert result["status"] == "not_assessed"
    assert result["uncertainty_minutes"] is None
    assert "samples" not in result
    assert result["continuous_interval_proven"] is False


@HAS_SWE
@pytest.mark.parametrize("radius", [0.0, 0.001, 0.7, 120.0])
def test_grid_covers_declared_endpoints_nominal_and_no_gaps_above_thirty_seconds(
    radius,
):
    birth = build_astro_birth_info(**STIMULUS)
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=radius)
    instants = [datetime.fromisoformat(s["recorded_utc"]) for s in result["samples"]]
    expected = timedelta(minutes=radius)
    assert instants[0] == birth.utc_datetime - expected
    assert instants[-1] == birth.utc_datetime + expected
    assert birth.utc_datetime in instants
    assert max(
        (b - a for a, b in zip(instants, instants[1:])), default=timedelta(0)
    ) <= timedelta(seconds=30)
    assert len(instants) <= 483
    assert result["sample_frequency_is_probability"] is False
    assert result["continuous_interval_proven"] is False
    if radius == 0:
        assert result["sample_count"] == 1


@HAS_SWE
def test_original_reading_at_nominal_time_is_not_present_across_the_declared_samples():
    result = calculate_germany_chart_analysis(
        **STIMULUS, birth_time_uncertainty_minutes=10
    )
    layer = result["midpoint_analysis"]
    assert len(layer["interpretations"]) == 1
    sensitivity = layer["time_sensitivity"]
    # Independent complex-phase residual reconstructs each declared decision.
    orbs = []
    for sample in sensitivity["samples"]:
        v = sample["factor_longitudes"]
        angle = math.radians(v["Mars"] + v["Jupiter"] - v["Zeus"] - v["Midheaven"])
        orbs.append(abs(math.degrees(math.atan2(math.sin(angle), math.cos(angle)))))
    present = sum(orb <= 2 for orb in orbs)
    pattern = sensitivity["source_pattern"]
    assert 0 < present < len(orbs)
    assert pattern["present_sample_count"] == present
    assert pattern["absent_sample_count"] == len(orbs) - present
    assert pattern["sampled_status"] == "varies_across_samples"
    assert pattern["minimum_sampled_direct_orb_degrees"] == pytest.approx(
        min(orbs), abs=1e-11
    )
    assert pattern["maximum_sampled_direct_orb_degrees"] == pytest.approx(
        max(orbs), abs=1e-11
    )
    assert (
        layer["interpretations"][0]["birth_time_sampled_status"]
        == "varies_across_samples"
    )
    for dial in layer["dials"].values():
        for row in dial["four_factor_contacts"]:
            if "source_interpretation" in row:
                assert (
                    row["source_interpretation"]["birth_time_sampled_status"]
                    == "varies_across_samples"
                )
    zero = calculate_germany_chart_analysis(
        **STIMULUS, birth_time_uncertainty_minutes=0
    )
    assert (
        zero["midpoint_analysis"]["time_sensitivity"]["source_pattern"][
            "sampled_status"
        ]
        == "present_at_every_sample"
    )


@HAS_SWE
def test_thirteen_sector_assignment_changes_with_real_recalculated_angles():
    result = calculate_core_chart_analysis(
        **STIMULUS, chart_variant="chart13", birth_time_uncertainty_minutes=10
    )
    sensitivity = result["time_sensitivity"]
    nominal = next(s for s in sensitivity["samples"] if s["offset_seconds"] == 0)
    for record in sensitivity["sector_assignments"]:
        reconstructed = []
        for sample in sensitivity["samples"]:
            v = sample["factor_longitudes"]
            # All this fixture's samples are away from exact rational edges.
            reconstructed.append(
                math.floor(((v[record["id"]] - v["Ascendant"]) % 360) * 13 / 360) + 1
            )
        assert record["sector_by_sample"] == reconstructed
        assert record["observed_sectors"] == sorted(set(reconstructed))
        index = sensitivity["samples"].index(nominal)
        assert record["nominal_sector"] == reconstructed[index]
    assert any(
        r["sampled_status"] == "varies_across_samples"
        for r in sensitivity["sector_assignments"]
    )
    # Independently re-run the public nominal chart at the actual endpoint.
    first = calculate_core_chart_analysis(
        **{**STIMULUS, "birth_minute": 20}, chart_variant="chart13"
    )
    assert [r["sector_by_sample"][0] for r in sensitivity["sector_assignments"]] == [
        p["sector13"] for p in first["planets"]
    ]


@HAS_SWE
def test_recorded_utc_grid_crosses_dst_fold_without_relocalizing_ambiguous_wall_times():
    birth = build_astro_birth_info(
        birth_year=2026,
        birth_month=11,
        birth_day=1,
        birth_hour=0,
        birth_minute=59,
        birth_timezone="America/New_York",
        birth_longitude=-74,
        birth_latitude=40.7,
    )
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=120)
    instants = [datetime.fromisoformat(s["recorded_utc"]) for s in result["samples"]]
    assert instants[-1] - instants[0] == timedelta(hours=4)
    assert all(b - a == timedelta(seconds=30) for a, b in zip(instants, instants[1:]))
    assert all(s["recorded_utc"] == s["effective_utc"] for s in result["samples"])


@HAS_SWE
def test_solar_clock_is_recomputed_before_factor_samples_and_nominal_is_preserved():
    payload = {
        **STIMULUS,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.4,
        "birth_latitude": 31.2,
        "use_true_solar_time": True,
    }
    birth = build_astro_birth_info(**payload)
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=1)
    assert (
        next(s["effective_utc"] for s in result["samples"] if s["offset_seconds"] == 0)
        == birth.utc_datetime.isoformat()
    )
    for sample in result["samples"]:
        offset = sample["offset_seconds"]
        recorded = birth.recorded_datetime + timedelta(seconds=offset)
        independently_rebuilt = build_astro_birth_info(
            **{
                **payload,
                "birth_hour": recorded.hour,
                "birth_minute": recorded.minute,
                "birth_second": recorded.second,
            }
        )
        assert sample["effective_utc"] == independently_rebuilt.utc_datetime.isoformat()


@HAS_SWE
@pytest.mark.parametrize("latitude", [-89.9, -70, 0, 70, 89.9])
def test_uncertainty_positions_rotate_together_under_lahiri_at_extreme_latitudes(
    latitude,
):
    birth = build_astro_birth_info(**{**STIMULUS, "birth_latitude": latitude})
    tropical = time_sensitivity(birth, sidereal=False, uncertainty_minutes=0)
    sidereal = time_sensitivity(birth, sidereal=True, uncertainty_minutes=0)
    t = tropical["samples"][0]["factor_longitudes"]
    s = sidereal["samples"][0]["factor_longitudes"]
    shift = t["Sun"] - s["Sun"]
    for name in t:
        assert (t[name] - s[name] - shift + 180) % 360 - 180 == pytest.approx(
            0, abs=1e-8
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 120.001])
def test_invalid_intervals_rejected_by_public_request_contract(value):
    with pytest.raises(ValidationError):
        AstroSpecialtyRequest.model_validate(
            {**astro_payload(), "birth_time_uncertainty_minutes": value}
        )


def test_polymorphic_options_are_scoped_without_silently_dropping_uncertainty():
    for variant in ("germany", "chart13", "india_chart"):
        model = AstroChartPolyRequest.model_validate(
            {
                **astro_payload(),
                "chart_variant": variant,
                "birth_time_uncertainty_minutes": 5,
            }
        )
        assert model.birth_time_uncertainty_minutes == 5
    for variant in ("chart", "guolao_chart", "hellen_chart"):
        with pytest.raises(ValidationError):
            AstroChartPolyRequest.model_validate(
                {
                    **astro_payload(),
                    "chart_variant": variant,
                    "birth_time_uncertainty_minutes": 5,
                }
            )
    with pytest.raises(ValidationError):
        AstroChartPolyRequest.model_validate(
            {**astro_payload(), "chart_variant": "germany", "node_mode": "true"}
        )


def test_explicit_interval_is_unavailable_if_swiss_is_missing(monkeypatch):
    birth = build_astro_birth_info(**STIMULUS)
    monkeypatch.setattr(runtime, "swe", None)
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=5)
    assert result["status"] == "unavailable"
    assert "samples" not in result


@HAS_SWE
def test_core_service_germany_dispatch_keeps_dedicated_geometry_and_uncertainty():
    direct = calculate_germany_chart_analysis(
        **STIMULUS, birth_time_uncertainty_minutes=0
    )
    generic = calculate_core_chart_analysis(
        **STIMULUS, chart_variant="germany", birth_time_uncertainty_minutes=0
    )
    assert direct == generic
