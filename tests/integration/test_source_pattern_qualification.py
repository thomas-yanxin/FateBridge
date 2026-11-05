"""Actual source conditions must not be inferred from a meridian convention."""

import copy
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.reference_angles import qualify_reference_geometry
from fatebridge.core.astro.source_pattern import (
    source_pattern_sample,
    source_pattern_summary,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from fatebridge.utils.errors import EphemerisSourceError

VECTORS = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/source-pattern-qualification.json"
    ).read_text()
)["rows"]
BIRTH = datetime(2000, 1, 1, 4, 30, tzinfo=timezone.utc)
PAYLOAD = dict(
    name="虚构：原文条件资格",
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=4,
    birth_minute=30,
    birth_timezone="UTC",
    birth_longitude=0,
    hsys=1,
)
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@pytest.mark.parametrize("row", VECTORS, ids=lambda row: row["id"])
def test_independently_frozen_vectors(row, monkeypatch):
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda *_: pytest.fail("Pure qualification must not query ephemeris"),
    )
    result = source_pattern_sample(
        row["values"], row["definition"], solar_arc_degrees=row["arc"]
    )
    assert result["reference_geometry_resolved"] is row["known"]
    assert result["condition_met"] is row["condition"]
    assert result["direct_orb_degrees"] == row["orb"]
    if not row["known"]:
        assert result["midheaven_longitude"] is None
        assert result["backend_condition_met"] is row["backend_condition"]
        assert result["backend_direct_orb_degrees"] == row["backend_orb"]
    else:
        v = row["values"]
        a = math.radians(
            v["Mars"] + v["Jupiter"] - v["Zeus"] - v["Midheaven"] - row["arc"]
        )
        assert result["direct_orb_degrees"] == pytest.approx(
            abs(math.degrees(math.atan2(math.sin(a), math.cos(a)))), abs=1e-12
        )


def test_inclusive_edge_and_adjacent_input_floats_are_not_rounded_into_a_hit():
    values = {"Mars": 10.0, "Jupiter": 20.0, "Zeus": 5.0, "Midheaven": 27.0}
    assert source_pattern_sample(values)["condition_met"] is True
    assert (
        source_pattern_sample({**values, "Midheaven": math.nextafter(27, math.inf)})[
            "condition_met"
        ]
        is False
    )
    assert (
        source_pattern_sample({**values, "Midheaven": math.nextafter(27, -math.inf)})[
            "condition_met"
        ]
        is True
    )


@pytest.mark.parametrize(
    "bad", [None, True, False, "25", float("inf"), float("-inf"), float("nan")]
)
def test_malformed_native_operands_are_typed_runtime_errors(bad):
    with pytest.raises(EphemerisSourceError) as exc:
        source_pattern_sample({**VECTORS[0]["values"], "Mars": bad})
    result = exc.value.as_result()
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "source_pattern_inputs"}
    ]


@pytest.mark.parametrize(
    "definition", [[], {"status": False}, {"status": None}, {"foo": "bar"}]
)
def test_malformed_reference_definitions_are_not_known_conditions(definition):
    with pytest.raises(EphemerisSourceError):
        source_pattern_sample(VECTORS[0]["values"], definition)


def test_known_absence_unknown_reference_and_unavailable_direction_are_distinct():
    rows = [
        source_pattern_sample(row["values"], row["definition"])
        for row in [VECTORS[0], VECTORS[1], VECTORS[5]]
    ] + [None]
    result = source_pattern_summary(rows)
    assert result["sampled_status"] == "underdetermined"
    assert (
        result["present_sample_count"],
        result["absent_sample_count"],
        result["unresolved_reference_sample_count"],
        result["unavailable_sample_count"],
    ) == (1, 1, 1, 1)
    assert result["condition_by_sample"] == [True, False, None, None]
    assert result["unresolved_reference_sample_indices"] == [2]
    assert result["resolved_condition_sample_count"] == 2
    assert result["minimum_sampled_direct_orb_degrees"] == 0
    assert result["maximum_sampled_direct_orb_degrees"] == 5
    assert result["backend_convention"]["condition_by_sample"] == [
        True,
        False,
        True,
        None,
    ]
    assert result["backend_convention"]["evaluable_sample_count"] == 3
    assert result["backend_convention"]["present_sample_count"] == 2
    assert source_pattern_summary([None])["sampled_status"] == "underdetermined"
    with pytest.raises(EphemerisSourceError):
        source_pattern_summary([])


def test_reference_reading_qualification_is_specific_and_idempotent():
    original = {"factor_longitudes": VECTORS[0]["values"], "reading_zh": "原先形式主题"}
    geometry = {"interpretations": [copy.deepcopy(original)]}
    qualify_reference_geometry(geometry, VECTORS[4]["definition"])
    assert geometry["interpretations"] == [original]
    qualify_reference_geometry(geometry, VECTORS[5]["definition"])
    once = copy.deepcopy(geometry)
    qualify_reference_geometry(geometry, VECTORS[5]["definition"])
    assert geometry == once
    reading = geometry["interpretations"][0]
    assert reading["source_application_status"] == "underdetermined_reference_geometry"
    assert reading["backend_reading_zh"] == "原先形式主题"
    assert reading["reading_zh"] != "原先形式主题"


@HAS_SWE
@pytest.mark.parametrize("latitude", [-90, 90])
@pytest.mark.parametrize("longitude", [0, 90])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_actual_pole_backend_hit_or_miss_never_counts_as_actual_condition(
    latitude, longitude, zodiacal
):
    result = calculate_germany_chart_analysis(
        **{**PAYLOAD, "birth_longitude": longitude},
        birth_latitude=latitude,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=BIRTH,
    )
    assert "error" not in result, result
    layer = result["midpoint_analysis"]
    assert (
        layer["profile"]["angle_definition"]["status"]
        == "geographic_pole_meridian_convention"
    )
    for sensitivity in [
        layer["time_sensitivity"],
        layer["solar_arc_analysis"]["birth_time_sensitivity"],
    ]:
        pattern = sensitivity["source_pattern"]
        assert pattern["sampled_status"] == "underdetermined"
        assert pattern["present_sample_count"] == pattern["absent_sample_count"] == 0
        assert pattern["unresolved_reference_sample_count"] == 1
        assert pattern["minimum_sampled_direct_orb_degrees"] is None
        assert pattern["maximum_sampled_direct_orb_degrees"] is None
        assert pattern["condition_by_sample"] == [None]
        assert pattern["backend_convention"]["present_sample_count"] == (
            1 if longitude == 0 else 0
        )
    for name in ["Ascendant", "Midheaven"]:
        span = layer["time_sensitivity"]["factor_spans"][name]
        assert span["status"] == f"underdetermined_{name.lower()}"
        assert span["minimum_offset_from_nominal_degrees"] is None
        assert (
            span["backend_convention_span"]["minimum_offset_from_nominal_degrees"] == 0
        )
    assert "status" not in layer["time_sensitivity"]["factor_spans"]["Sun"]
    for reading in (
        layer["interpretations"] + layer["solar_arc_analysis"]["interpretations"]
    ):
        assert reading["physical_reference_geometry_resolved"] is False
        assert (
            reading["source_application_status"] == "underdetermined_reference_geometry"
        )
        assert reading["birth_time_sampled_status"] == "underdetermined"
        assert reading["backend_reading_zh"] != reading["reading_zh"]
    if longitude == 0:
        assert (
            layer["interpretations"] and layer["solar_arc_analysis"]["interpretations"]
        )
    directed = layer["solar_arc_analysis"]["birth_time_sensitivity"]["samples"][0]
    assert directed["source_condition_met"] is None
    assert directed["source_direct_orb_degrees"] is None
    assert directed["directed_midheaven_longitude"] is None
    assert directed["backend_convention"]["source_condition_met"] is (longitude == 0)
    assert directed["solar_arc_degrees"] == 0


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("radius", [None, 0.5])
def test_unknown_interval_and_complete_grid_keep_distinct_unknowns(zodiacal, radius):
    target = BIRTH if radius is None else datetime(2050, 1, 1, tzinfo=timezone.utc)
    result = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_latitude=90,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=radius,
        analysis_datetime=target,
    )
    layer = result["midpoint_analysis"]
    for s in [
        layer["time_sensitivity"],
        layer["solar_arc_analysis"]["birth_time_sensitivity"],
    ]:
        if radius is None:
            assert (
                s["status"] == "not_assessed"
                and "samples" not in s
                and "source_pattern" not in s
            )
        else:
            assert s["sample_count"] == 3
            p = s["source_pattern"]
            assert p["condition_by_sample"] == [None] * 3
            assert p["present_sample_count"] == p["absent_sample_count"] == 0
            assert p["unresolved_reference_sample_indices"] == [0, 1, 2]
    if radius is None:
        assert all(
            r["source_application_status"] == "underdetermined_reference_geometry"
            for r in layer["interpretations"]
            + layer["solar_arc_analysis"]["interpretations"]
        )


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_only_unresolved_ascendant_does_not_make_the_source_midheaven_unknown(zodiacal):
    result = calculate_germany_chart_analysis(
        **{
            **PAYLOAD,
            "birth_hour": 12,
            "birth_minute": 0,
            "birth_longitude": 169.5414439374805,
        },
        birth_latitude=-66.56232328397007,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=1,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    layer = result["midpoint_analysis"]
    samples = layer["time_sensitivity"]["samples"]
    assert samples[2]["angle_definition"]["geometric_ascendant_resolved"] is False
    for s in [
        layer["time_sensitivity"],
        layer["solar_arc_analysis"]["birth_time_sensitivity"],
    ]:
        p = s["source_pattern"]
        assert "unresolved_reference_sample_count" not in p
        assert p["present_sample_count"] + p["absent_sample_count"] == 5
    assert "status" not in layer["time_sensitivity"]["factor_spans"]["Midheaven"]


@HAS_SWE
@pytest.mark.parametrize("latitude", [-89.9, 89.9])
def test_resolved_near_pole_meridian_is_not_replaced_by_an_unknown(latitude):
    result = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_latitude=latitude,
        birth_time_uncertainty_minutes=0,
        analysis_datetime=BIRTH,
    )
    layer = result["midpoint_analysis"]
    for sensitivity in (
        layer["time_sensitivity"],
        layer["solar_arc_analysis"]["birth_time_sensitivity"],
    ):
        pattern = sensitivity["source_pattern"]
        assert pattern["present_sample_count"] == 1
        assert pattern["absent_sample_count"] == 0
        assert "unresolved_reference_sample_count" not in pattern
    assert "status" not in layer["time_sensitivity"]["factor_spans"]["Midheaven"]


@HAS_SWE
@pytest.mark.parametrize("latitude", [-90, 90])
def test_equal13_shares_span_qualification_and_retains_its_declared_partition(latitude):
    result = calculate_core_chart_analysis(
        **PAYLOAD,
        birth_latitude=latitude,
        birth_time_uncertainty_minutes=0.5,
        chart_variant="chart13",
    )
    assert "error" not in result, result
    for name in ("Ascendant", "Midheaven"):
        span = result["time_sensitivity"]["factor_spans"][name]
        assert span["status"] == f"underdetermined_{name.lower()}"
        assert span["unresolved_sample_count"] == 3
        assert span["minimum_offset_from_nominal_degrees"] is None
    assert len(result["thirteen_sectors"]) == 13
    assert all(p["sector13"] is not None for p in result["planets"])
    assert all(
        None not in row["sector_by_sample"]
        for row in result["time_sensitivity"]["sector_assignments"]
    )


@HAS_SWE
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("key_years", [0, 150])
def test_unavailable_arc_and_unknown_reference_are_both_retained(zodiacal, key_years):
    result = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_latitude=90,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=1,
        analysis_datetime=BIRTH + timedelta(days=365.25 * key_years),
    )
    s = result["midpoint_analysis"]["solar_arc_analysis"]["birth_time_sensitivity"]
    p = s["source_pattern"]
    assert s["status"] == "partial" and s["sample_count"] == 5
    assert s["computed_sample_count"] == 3 and s["unavailable_sample_count"] == 2
    assert s["unresolved_reference_sample_count"] == 3
    assert (
        p["present_sample_count"]
        == p["absent_sample_count"]
        == p["resolved_condition_sample_count"]
        == 0
    )
    assert (
        p["unresolved_reference_sample_count"] == 3
        and p["unavailable_sample_count"] == 2
    )
    assert p["condition_by_sample"] == [None] * 5
    assert p["backend_convention"]["evaluable_sample_count"] == 3
    for row in s["samples"]:
        assert row.get("source_condition_met") is None
        if row.get("status") == "unavailable":
            assert "backend_convention" not in row and "solar_arc_degrees" not in row
        else:
            assert row["solar_arc_degrees"] is not None and "backend_convention" in row


@HAS_SWE
def test_corrupt_derived_native_source_is_503_not_invalid_birth(monkeypatch):
    import fatebridge.core.astro.sensitivity as module

    original = module.source_pattern_sample

    def corrupt(values, definition):
        return original({**values, "Mars": float("inf")}, definition)

    monkeypatch.setattr(module, "source_pattern_sample", corrupt)
    result = calculate_germany_chart_analysis(
        **PAYLOAD, birth_latitude=20, birth_time_uncertainty_minutes=0
    )
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "source_pattern_inputs"}
    ]
