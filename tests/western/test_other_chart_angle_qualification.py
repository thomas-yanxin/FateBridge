"""Native specialty paths must not promote an unresolved ASC to an assignment."""

from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.reference_angles import qualify_reference_geometry
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)

PAYLOAD = dict(
    name="虚构：黄道地平面退化核验",
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
    birth_time_uncertainty_minutes=1,
    hsys=1,
)
# The original locations are ill-conditioned under the current source equator.
# Keep their input values and add truly unresolved controls for the same clock.
LOCATIONS = [
    (169.5414439374805, -66.56232328397007),
    (-10.4585560625195, 66.56232328397007),
]
# Swiss 2.10.03 source ecliptic, SOFA 2023-10-11, 100-digit eastern intersection.
# See R59 western-specialty-angle/authority-observed/reference.json.
NULL_LOCATIONS = [
    (169.54144401512139, -66.5623231709126),
    (-10.458555984878615, 66.5623231709126),
]
RESOLVED_ASCENDANTS = [
    (195.27771505145736, 171.42449256526297),
    (15.277715051457369, 351.42449256526294),
]
# R59 near-null-observed/reference.json, independent south location +1e-9°.
NEAR_NULL_SOUTH = (169.54144401612137, -66.5623231699126)
NEAR_NULL_ASCENDANT = 201.69011421515978


def assert_ill_conditioned_ascendant(definition, actual, expected):
    assert definition["status"] == "ecliptic_horizon_ill_conditioned"
    assert definition["geometric_ascendant_resolved"] is True
    assert abs((actual - expected + 180) % 360 - 180) * 3600 <= 1


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("longitude,latitude", LOCATIONS)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_native_germany_qualifies_only_dependent_geometry(
    longitude, latitude, zodiacal: int
) -> None:
    site = LOCATIONS.index((longitude, latitude))
    analysis = dict(
        **PAYLOAD,
        zodiacal=zodiacal,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
    )
    resolved = calculate_germany_chart_analysis(
        **analysis,
        birth_longitude=longitude,
        birth_latitude=latitude,
    )["midpoint_analysis"]
    assert_ill_conditioned_ascendant(
        resolved["profile"]["angle_definition"],
        next(
            row["longitude"] for row in resolved["factors"] if row["id"] == "Ascendant"
        ),
        RESOLVED_ASCENDANTS[site][zodiacal],
    )
    assert "status" not in resolved["time_sensitivity"]["factor_spans"]["Ascendant"]

    null_longitude, null_latitude = NULL_LOCATIONS[site]
    result = calculate_germany_chart_analysis(
        **analysis,
        birth_longitude=null_longitude,
        birth_latitude=null_latitude,
    )
    assert "error" not in result, result
    assert result["base_chart"]["chart_profile"]["house_system"] == "alcabitus"
    assert result["base_chart"]["chart_profile"]["house_system_code"] == 1
    native = result["midpoint_analysis"]
    definition = native["profile"]["angle_definition"]
    assert definition["geometric_ascendant_resolved"] is False
    assert definition["status"] == "ecliptic_horizon_numerically_unresolved"
    assert len(native["factors"]) == 22
    factors = {f["id"]: f for f in native["factors"]}
    assert factors["Ascendant"]["coordinate_basis"] == "backend_numeric_convention_only"
    assert "coordinate_basis" not in factors["Midheaven"]
    assert "coordinate_basis" not in factors["Sun"]
    for geometry in [native, native["solar_arc_analysis"]]:
        assert geometry["status"] == "computed"
        dependent = 0
        for dial in geometry["dials"].values():
            for field in [
                "two_factor_contacts",
                "three_factor_contacts",
                "four_factor_contacts",
            ]:
                for row in dial[field]:
                    names = {
                        row[k]
                        for k in ["point", "id_a", "id_b", "id_c", "id_d"]
                        if k in row
                    }
                    if "Ascendant" in names:
                        dependent += 1
                        assert row["reference_angle_basis"] == {
                            "Ascendant": "backend_numeric_convention_only"
                        }
                        assert row["physical_reference_geometry_resolved"] is False
                    else:
                        assert "reference_angle_basis" not in row
        assert dependent > 0
    mixed_dependent = 0
    for dial in native["solar_arc_analysis"]["mixed_pair_geometry"]["dials"].values():
        for field in ("arc_dependent_contacts", "arc_invariant_contacts"):
            for row in dial[field]:
                names = {row[k] for k in ("id_a", "id_b", "id_c", "id_d")}
                if "Ascendant" in names:
                    mixed_dependent += 1
                    assert row["reference_angle_basis"] == {
                        "Ascendant": "backend_numeric_convention_only"
                    }
                    assert row["physical_reference_geometry_resolved"] is False
                else:
                    assert "reference_angle_basis" not in row
    assert mixed_dependent > 0
    mixed_sensitivity = native["solar_arc_analysis"]["mixed_pair_geometry"][
        "birth_time_sensitivity"
    ]
    assert mixed_sensitivity["status"] == "partial"
    assert mixed_sensitivity["nominal_sample_index"] == 2
    for dial in mixed_sensitivity["dials"].values():
        for row in dial["contacts"]:
            if "Ascendant" in {row[k] for k in ("id_a", "id_b", "id_c", "id_d")}:
                assert row["nominal_condition"] is None
                assert 2 in row["unknown_sample_indices"]
            else:
                pass
    sensitivity = native["time_sensitivity"]
    assert len(sensitivity["samples"]) == sensitivity["sample_count"] == 5
    assert (
        sensitivity["samples"][2]["angle_definition"]["geometric_ascendant_resolved"]
        is False
    )
    span = sensitivity["factor_spans"]["Ascendant"]
    assert span["status"] == "underdetermined_ascendant"
    assert span["minimum_offset_from_nominal_degrees"] is None
    assert span["unresolved_sample_count"] == 1
    assert "backend_convention_span" in span
    assert "status" not in sensitivity["factor_spans"]["Midheaven"]
    assert native["meridian_houses"]["status"] == "computed"
    assert native["solar_arc_analysis"]["daily_meridian"]["status"] == "computed"


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("longitude,latitude", LOCATIONS)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_equal13_keeps_unknown_samples_and_replay_conventions(
    longitude, latitude, zodiacal: int
) -> None:
    site = LOCATIONS.index((longitude, latitude))
    analysis = dict(**PAYLOAD, zodiacal=zodiacal, chart_variant="chart13")
    resolved = calculate_core_chart_analysis(
        **analysis,
        birth_longitude=longitude,
        birth_latitude=latitude,
    )
    assert "error" not in resolved, resolved
    assert_ill_conditioned_ascendant(
        resolved["sector_profile"]["angle_definition"],
        resolved["sector_profile"]["anchor_longitude"],
        RESOLVED_ASCENDANTS[site][zodiacal],
    )
    assert len(resolved["thirteen_sectors"]) == 13
    assert all(
        len(row["sector_by_sample"]) == 5 and None not in row["sector_by_sample"]
        for row in resolved["time_sensitivity"]["sector_assignments"]
    )

    null_longitude, null_latitude = NULL_LOCATIONS[site]
    result = calculate_core_chart_analysis(
        **analysis,
        birth_longitude=null_longitude,
        birth_latitude=null_latitude,
    )
    assert "error" not in result, result
    assert result["chart_profile"]["house_system"] == "alcabitus"
    assert result["chart_profile"]["house_system_code"] == 1
    profile = result["sector_profile"]
    assert profile["status"] == "underdetermined_ascendant"
    assert profile["anchor_longitude"] is None
    assert len(profile["backend_convention_sectors"]) == 13
    assert result["thirteen_sectors"] == []
    assert result["planets"]
    assert all(planet["sector13"] is None for planet in result["planets"])
    for planet in result["planets"]:
        assert planet["longitude"] is not None
        assert (
            planet["sector13_evidence"]["assignment_status"]
            == "underdetermined_ascendant"
        )
        assert 1 <= planet["sector13_evidence"]["backend_convention_sector"] <= 13
    samples = result["time_sensitivity"]["samples"]
    assert len(samples) == 5
    for row in result["time_sensitivity"]["sector_assignments"]:
        assert row["sampled_status"] == "underdetermined"
        assert row["computed_sample_count"] == 4
        assert row["unresolved_sample_count"] == 1
        assert row["nominal_sector"] is None
        assert len(row["sector_by_sample"]) == 5
        assert row["sector_by_sample"][2] is None
        assert row["observed_sectors"] == sorted(
            {v for v in row["sector_by_sample"] if v is not None}
        )


def test_reference_qualification_does_not_relabel_unrelated_geometry() -> None:
    geometry = {
        "midpoint_axes": [
            {"id_a": "Sun", "id_b": "Midheaven"},
            {"id_a": "Moon", "id_b": "Ascendant"},
        ]
    }
    qualify_reference_geometry(
        geometry,
        {
            "status": "ecliptic_horizon_numerically_unresolved",
            "retained_ascendant_role": "backend_numeric_convention_only",
        },
    )
    assert "reference_angle_basis" not in geometry["midpoint_axes"][0]
    assert geometry["midpoint_axes"][1]["physical_reference_geometry_resolved"] is False


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("mode", ["ill_conditioned", "geographic_pole"])
def test_resolved_or_meridian_convention_is_not_discarded_as_unresolved(
    mode: str,
) -> None:
    longitude, latitude = LOCATIONS[0]
    latitude = latitude + 1e-8 if mode == "ill_conditioned" else 90.0
    result = calculate_core_chart_analysis(
        **PAYLOAD,
        birth_longitude=longitude,
        birth_latitude=latitude,
        chart_variant="chart13",
    )
    assert "error" not in result, result
    definition = result["sector_profile"]["angle_definition"]
    if mode == "ill_conditioned":
        assert definition["geometric_ascendant_resolved"] is True
        assert definition["status"] == "ecliptic_horizon_ill_conditioned"
    else:
        assert definition["status"] == "geographic_pole_meridian_convention"
        assert definition["fixed_direction_diurnal_rising_defined"] is False
    assert "status" not in result["sector_profile"]
    assert len(result["thirteen_sectors"]) == 13
    assert all(planet["sector13"] is not None for planet in result["planets"])
    assert all(
        None not in row["sector_by_sample"]
        for row in result["time_sensitivity"]["sector_assignments"]
    )


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("radius", [None, 0])
def test_unknown_and_zero_uncertainty_do_not_resolve_the_nominal_ascendant(
    radius: int | None,
) -> None:
    longitude, latitude = LOCATIONS[0]
    analysis = {
        **PAYLOAD,
        "birth_time_uncertainty_minutes": radius,
        "chart_variant": "chart13",
    }
    resolved = calculate_core_chart_analysis(
        **analysis,
        birth_longitude=longitude,
        birth_latitude=latitude,
    )
    assert "error" not in resolved, resolved
    assert_ill_conditioned_ascendant(
        resolved["sector_profile"]["angle_definition"],
        resolved["sector_profile"]["anchor_longitude"],
        RESOLVED_ASCENDANTS[0][0],
    )
    if radius is None:
        assert resolved["time_sensitivity"]["status"] == "not_assessed"
        assert "samples" not in resolved["time_sensitivity"]
    else:
        assert resolved["time_sensitivity"]["sample_count"] == 1
        assert all(
            row["sector_by_sample"] == [row["nominal_sector"]]
            for row in resolved["time_sensitivity"]["sector_assignments"]
        )

    null_longitude, null_latitude = NULL_LOCATIONS[0]
    result = calculate_core_chart_analysis(
        **analysis,
        birth_longitude=null_longitude,
        birth_latitude=null_latitude,
    )
    assert "error" not in result, result
    assert result["sector_profile"]["status"] == "underdetermined_ascendant"
    assert all(planet["sector13"] is None for planet in result["planets"])
    sensitivity = result["time_sensitivity"]
    if radius is None:
        assert sensitivity["status"] == "not_assessed"
        assert "samples" not in sensitivity
    else:
        assert sensitivity["sample_count"] == 1
        assert all(
            row["sector_by_sample"] == [None] and row["computed_sample_count"] == 0
            for row in sensitivity["sector_assignments"]
        )
