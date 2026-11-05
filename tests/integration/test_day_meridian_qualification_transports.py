"""Actual specialty transports and independent reconstruction of returned inputs."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import three_surfaces


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "north",
        "south",
        "asc_only",
        "range_start",
        "range_end",
        "unknown_interval",
        "solar_clock",
    ],
)
def test_day_reference_and_source_coherence_across_real_surfaces(
    key, variant, zodiacal, mode, tmp_path, monkeypatch, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    target = datetime(2050, 1, 1, tzinfo=timezone.utc)
    payload = dict(
        name="虚构：日推运资格三端核验",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=10,
        birth_latitude=20,
        hsys=1,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=0.5,
    )
    if variant:
        payload["chart_variant"] = variant
    if mode in ("north", "south"):
        payload.update(
            birth_latitude=90 if mode == "north" else -90,
            birth_time_uncertainty_minutes=0,
        )
        target = birth
    elif mode == "asc_only":
        payload.update(
            birth_latitude=-66.56232328397007,
            birth_longitude=169.5414439374805,
            birth_time_uncertainty_minutes=1,
        )
    elif mode in ("range_start", "range_end"):
        payload.update(birth_latitude=90, birth_time_uncertainty_minutes=1)
        target = birth + timedelta(days=(0 if mode == "range_start" else 150) * 365.25)
    elif mode == "unknown_interval":
        payload.update(birth_latitude=90, birth_time_uncertainty_minutes=None)
    elif mode == "solar_clock":
        payload.pop("birth_timezone")
        payload.update(
            birth_clock_basis="local_apparent_solar", birth_time_uncertainty_minutes=0.7
        )
    payload["analysis_datetime"] = target.isoformat()
    fields = [
        "midpoint_analysis.profile",
        "midpoint_analysis.factors",
        "midpoint_analysis.time_sensitivity",
        "midpoint_analysis.solar_arc_analysis.profile",
        "midpoint_analysis.solar_arc_analysis.daily_meridian",
    ]
    body = three_surfaces(
        spec, payload, fields, target.isoformat(), tmp_path, monkeypatch, capsys
    )
    layer = body["midpoint_analysis"]
    solar = layer["solar_arc_analysis"]
    day = solar["daily_meridian"]
    profile = day["profile"]
    sensitivity = day["birth_time_sensitivity"]
    assert day["input_coherence"]["status"] == "verified"
    assert (
        day["input_coherence"]["birth_julian_day_tt"]
        == layer["profile"]["julian_day_tt"]
    )
    values = {r["id"]: r["longitude"] for r in layer["factors"]}
    phase = math.radians(
        values["Midheaven"]
        + solar["profile"]["solar_arc_degrees"]
        - solar["profile"]["natal_tropical_sun"]
        + profile["target_tropical_sun"]
    )
    expected = math.degrees(math.atan2(math.sin(phase), math.cos(phase))) % 360
    unresolved = mode in (
        "north",
        "south",
        "range_start",
        "range_end",
        "unknown_interval",
    )
    coords = profile["backend_convention"] if unresolved else profile
    assert coords["upper_meridian_longitude"] == pytest.approx(
        expected, abs=1e-10, rel=0
    )
    if unresolved:
        assert (
            profile["upper_meridian_longitude"] is None and day["status"] == "partial"
        )
    else:
        assert day["status"] == "computed"
    if mode == "unknown_interval":
        assert sensitivity["status"] == "not_assessed" and "samples" not in sensitivity
        assert day["input_coherence"]["sample_count"] is None
        return
    raw = layer["time_sensitivity"]["samples"]
    samples = sensitivity["samples"]
    assert len(samples) == len(raw) == day["input_coherence"]["sample_count"]
    for native, row in zip(raw, samples):
        assert (
            row["offset_seconds"] == native["offset_seconds"]
            and row["effective_utc"] == native["effective_utc"]
            and row["julian_day_tt"] == native["julian_day_tt"]
        )
        if row.get("status") == "unavailable":
            assert mode in ("range_start", "range_end")
            assert "backend_convention" not in row and "solar_arc_degrees" not in row
            continue
        phase = math.radians(
            native["factor_longitudes"]["Midheaven"]
            + row["solar_arc_degrees"]
            - row["natal_tropical_sun"]
            + profile["target_tropical_sun"]
        )
        expected = math.degrees(math.atan2(math.sin(phase), math.cos(phase))) % 360
        computed = row["backend_convention"] if unresolved else row
        assert computed["upper_meridian_longitude"] == pytest.approx(
            expected, abs=1e-10, rel=0
        )
        observations = solar["profile"]["sun_ephemeris_source"]["observations"]
        n, p = (observations[i] for i in row["sun_observation_indices"])
        assert (
            n["julian_day_tt"] == row["julian_day_tt"]
            and n["longitude"] == row["natal_tropical_sun"]
        )
        assert p["julian_day_tt"] == row["progressed_julian_day_tt"]
    if mode in ("range_start", "range_end"):
        assert (
            sensitivity["unavailable_sample_count"] == 2
            and sensitivity["unresolved_reference_sample_count"] == 3
        )
    if mode == "asc_only":
        assert profile["angle_definition"]["geometric_ascendant_resolved"] is False
        assert profile["upper_meridian_longitude"] is not None
    if mode == "solar_clock":
        assert sensitivity["input_clock_basis"] == "local_apparent_solar"
