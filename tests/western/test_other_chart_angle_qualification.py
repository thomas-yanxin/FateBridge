"""Native specialty paths must not promote an unresolved ASC to an assignment."""

import math
from datetime import datetime, timezone
from fractions import Fraction

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.reference_angles import qualify_reference_geometry
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from tests.support.transports import AS_OF, SPECS, three_surfaces

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
# These two synthetic locations make ARMC90/270 and phi=+/- (90-eps)
# in the current physical house-angle model at this UTC instant. Older native
# frame fixtures now describe resolved, ill-conditioned intersections.
CLASSICAL_LOCATION = (169.54144401512139, -66.5623231709126)
LOCATIONS = [
    CLASSICAL_LOCATION,
    (CLASSICAL_LOCATION[0] - 180, -CLASSICAL_LOCATION[1]),
]
# Dedicated Hellenistic requests have no birth-time-sensitivity control.
CLASSICAL_PAYLOAD = {
    key: value
    for key, value in PAYLOAD.items()
    if key != "birth_time_uncertainty_minutes"
}


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("longitude,latitude", LOCATIONS)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_native_germany_qualifies_only_dependent_geometry(
    longitude, latitude, zodiacal
):
    result = calculate_germany_chart_analysis(
        **PAYLOAD,
        birth_longitude=longitude,
        birth_latitude=latitude,
        zodiacal=zodiacal,
        analysis_datetime=datetime(2050, 1, 1, tzinfo=timezone.utc),
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
    longitude, latitude, zodiacal
):
    result = calculate_core_chart_analysis(
        **PAYLOAD,
        birth_longitude=longitude,
        birth_latitude=latitude,
        zodiacal=zodiacal,
        chart_variant="chart13",
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


def test_reference_qualification_does_not_relabel_unrelated_geometry():
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
def test_resolved_or_meridian_convention_is_not_discarded_as_unresolved(mode):
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
def test_unknown_and_zero_uncertainty_do_not_resolve_the_nominal_ascendant(radius):
    longitude, latitude = LOCATIONS[0]
    result = calculate_core_chart_analysis(
        **{**PAYLOAD, "birth_time_uncertainty_minutes": radius},
        birth_longitude=longitude,
        birth_latitude=latitude,
        chart_variant="chart13",
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


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("spec_key", ["astro_chart", "astro_hellen"])
@pytest.mark.parametrize(
    "case", ["singular", "south", "north", "ordinary", "mc_houses"]
)
def test_classical_angle_dependencies_three_surfaces(
    spec_key, case, tmp_path, monkeypatch, capsys
):
    longitude, latitude = CLASSICAL_LOCATION
    if case == "south":
        latitude -= 1e-8
    elif case == "north":
        latitude += 1e-8
    elif case == "ordinary":
        longitude, latitude = 0.0, 30.0
    payload = {
        **CLASSICAL_PAYLOAD,
        "birth_longitude": longitude,
        "birth_latitude": latitude,
        "hsys": 8 if case == "mc_houses" else 0,
    }
    fields = [
        "chart_profile",
        "classical",
        "planets",
        "planetary_hours",
        "angles",
        "houses",
    ]
    if spec_key == "astro_hellen":
        fields.append("hellenistic")
    result = three_surfaces(
        SPECS[spec_key], payload, fields, AS_OF, tmp_path, monkeypatch, capsys
    )
    unresolved = case in {"singular", "mc_houses"}
    houses_resolved = not unresolved or case == "mc_houses"
    classical = result["classical"]
    definition = result["chart_profile"].get("angle_definition")
    if case != "ordinary":
        assert definition["geometric_ascendant_resolved"] is not unresolved
        # Independent altitude-equation check against actual model inputs.
        inputs = definition["geometry_inputs"]
        phi, theta, eps = map(
            math.radians, (latitude, inputs["armc"], inputs["obliquity"])
        )
        norm = math.hypot(
            math.cos(phi) * math.cos(theta),
            math.cos(phi) * math.sin(theta) * math.cos(eps)
            + math.sin(phi) * math.sin(eps),
        )
        assert (norm <= 64 * math.ulp(1.0)) is unresolved
    assert len(classical["ptolemy"]["planets"]) == 7
    assert len(classical["ptolemy"]["sign_relationships"]) == 21
    assert classical["dispositors"]["chains"]["Sun"]["chain"]
    assert classical["sect"] in {"day", "night"}
    assert classical["syzygy"]["solver"]["strictly_before_birth"]
    assert all(p["longitude"] is not None for p in result["planets"])
    assert len(classical["topic_almutens"]) == (12 if houses_resolved else 0)
    for name, planet in classical["planets"].items():
        assert (planet["angularity"] is not None) is houses_resolved
        assert (planet["joy"] is not None) is houses_resolved
        if name in classical["ptolemy"]["planets"]:
            assert planet["essential"]
        assert planet["dodekatemorion"]
        assert planet["above_horizon"] is not None
    figuris = classical["almuten_figuris"]
    temperament = classical["temperament"]
    if unresolved:
        assert classical["lots"] == {}
        assert classical["ptolemy"]["lot_of_fortune"] is None
        assert figuris["winner"] is figuris["totals"] is None
        assert figuris["status"] == "partial"
        assert figuris["unknown_points"] == ["Ascendant", "fortune"]
        assert set(figuris["points"]) == {"Sun", "Moon", "syzygy"}
        totals = {}
        for point in figuris["points"].values():
            for planet, score in point["totals"].items():
                totals[planet] = totals.get(planet, 0) + score
        assert figuris["known_totals"] == totals
        assert temperament["status"] == "partial"
        assert temperament["unknown_components"] == [
            "ascendant_sign",
            "ascendant_ruler",
        ]
        assert temperament["tally"] is temperament["humor"] is None
        # Sun Capricorn (cold/dry), Moon Scorpio (cold/moist), plus the
        # Sun (hot/dry) and Moon (cold/moist); no ASC or ASC-ruler weights.
        assert temperament["known_tally"] == {"hot": 1, "cold": 3, "dry": 2, "moist": 2}
    else:
        assert set(classical["lots"]) == {"fortune", "spirit", "marriage", "children"}
        assert set(figuris["points"]) == {
            "Sun",
            "Moon",
            "Ascendant",
            "fortune",
            "syzygy",
        }
        assert figuris["winner"] and temperament["humor"]
        positions = {p["id"]: Fraction(p["longitude"]) for p in result["planets"]}
        asc = Fraction(result["angles"]["ascendant"]["longitude"])
        expected_ptolemy = float((asc + positions["Moon"] - positions["Sun"]) % 360)
        assert classical["ptolemy"]["lot_of_fortune"]["longitude"] == expected_ptolemy
        expected_lot = float(
            (
                asc + positions["Moon"] - positions["Sun"]
                if classical["sect"] == "day"
                else asc + positions["Sun"] - positions["Moon"]
            )
            % 360
        )
        assert classical["lots"]["fortune"]["longitude"] == expected_lot
        if case == "ordinary":
            assert result["planetary_hours"]["hour_ruler"]
    if spec_key == "astro_hellen":
        hellen = result["hellenistic"]
        assert (hellen["ascendant_ruler"] is None) is unresolved
        assert (hellen["lot_of_fortune"] is None) is unresolved
        assert (hellen["angular_planets"] is not None) is houses_resolved
        if not unresolved:
            assert (
                hellen["lot_of_fortune"]["longitude"]
                == classical["lots"]["fortune"]["longitude"]
            )


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("spec_key", ["astro_chart", "astro_hellen"])
def test_unresolved_classical_null_leaf_projection(
    spec_key, tmp_path, monkeypatch, capsys
):
    longitude, latitude = CLASSICAL_LOCATION
    result = three_surfaces(
        SPECS[spec_key],
        {
            **CLASSICAL_PAYLOAD,
            "birth_longitude": longitude,
            "birth_latitude": latitude,
            "hsys": 0,
        },
        [
            "classical.ptolemy.lot_of_fortune",
            "classical.almuten_figuris.winner",
            "classical.temperament.humor",
            "classical.temperament.known_tally",
        ],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )
    assert result["classical"]["ptolemy"]["lot_of_fortune"] is None
    assert result["classical"]["almuten_figuris"]["winner"] is None
    assert result["classical"]["temperament"]["humor"] is None


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("hsys", [0, 8])
@pytest.mark.parametrize("fortune_method", ["sect_reversing", "ptolemy_iii10"])
def test_unresolved_classical_optional_context_and_snapshot(hsys, fortune_method):
    from fatebridge.services.astrology import _build_standard_chart_snapshot_sections

    longitude, latitude = CLASSICAL_LOCATION
    birth = build_astro_birth_info(
        name="synthetic",
        birth_place="",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=longitude,
        birth_latitude=latitude,
        use_true_solar_time=False,
    )
    result = build_core_chart_payload(
        birth,
        "hellen_chart",
        hsys=hsys,
        include_context_geometry=True,
        context_fortune_method=fortune_method,
    )
    context = result["context_geometry"]
    assert context["fortune_definition"]["status"] == "underdetermined_ascendant"
    assert context["angles"]["ascendant"] is None
    assert context["angles"]["midheaven"] == result["angles"]["midheaven"]["longitude"]
    assert "Pars Fortuna" not in {obj["id"] for obj in context["objects"]}
    assert context["objects"] and all(
        obj["lon"] is not None for obj in context["objects"]
    )
    assert all((obj["house"] is not None) == (hsys == 8) for obj in context["objects"])
    assert len(context["houses"]) == (12 if hsys == 8 else 0)
    assert all(hit["point"] != "Ascendant" for hit in result["fixed_stars"])
    sections = dict(
        _build_standard_chart_snapshot_sections(result, chart_variant="hellen_chart")
    )
    for title in ["命主", "体质", "阿拉伯点"]:
        assert "未知" in sections[title]
    assert "日→" in sections["命主"] and "月→" in sections["命主"]
    if hsys == 0:
        assert "未知" in sections["宫主星"]
    else:
        assert "未知" not in sections["宫主星"]
    assert "福点：未知" in "\n".join(sections.values())


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize(
    "longitude,latitude",
    [(169.5414439374805, -66.56232328397007), (-10.4585560625195, 66.56232328397007)],
)
def test_old_native_frame_fixture_is_resolved_in_physical_model(longitude, latitude):
    from fatebridge.core.astro.angle_definitions import (
        native_ecliptic_horizon_angle_definition,
    )

    # Frozen TT/UT1 for 2000-01-01T12:00:00Z under the baseline physical house
    # model. ARMC's longitude offset preserves the same physical meridian epoch.
    armc = (90.0 + longitude - CLASSICAL_LOCATION[0]) % 360
    definition = native_ecliptic_horizon_angle_definition(
        julian_day_ut1=2451545.00000411,
        julian_day_tt=2451545.0007428704,
        latitude=latitude,
        armc=armc,
    )
    assert definition["status"] == "ecliptic_horizon_ill_conditioned"
    assert definition["geometric_ascendant_resolved"] is True
    conditioning = definition["conditioning"]
    assert (
        conditioning["float_resolution_guard"]
        < conditioning["intersection_normal_norm"]
    )
    assert (
        conditioning["intersection_normal_norm"] < conditioning["condition_threshold"]
    )
