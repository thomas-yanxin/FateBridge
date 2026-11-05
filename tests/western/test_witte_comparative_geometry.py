"""Source arithmetic, independent vectors and qualified same-run sample reuse."""

import importlib.util
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.comparative import (
    FRAMES,
    build_comparative_geometry,
    comparative_coordinates,
)
from fatebridge.core.output_midpoints import ComparativeGeometry
from fatebridge.utils.errors import EphemerisSourceError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/uranian-witte1924-comparative.json"


def values():
    return {
        "Aries Point": 0.0,
        "Sun": 13.25,
        "Moon": 45.5,
        "North Node": 123.75,
        "Midheaven": 217.25,
        "Ascendant": 332.5,
        "Uranus": 114.45,
    }


def inputs(radius=None, definition=None):
    v = values()
    layer = {
        "status": "computed",
        "factors": [{"id": k, "longitude": x} for k, x in v.items()],
        "profile": {"zodiac": "tropical", "julian_day_tt": 2451545.0},
    }
    if definition:
        layer["profile"]["angle_definition"] = definition
    uncertainty = {"status": "not_assessed", "uncertainty_minutes": None}
    if radius is not None:
        offsets = [0] if radius == 0 else [-30, 0, 30]
        samples = []
        for offset in offsets:
            sample = {
                "offset_seconds": offset,
                "recorded_utc": f"synthetic-recorded:{offset}",
                "effective_utc": f"synthetic-effective:{offset}",
                "julian_day_tt": 2451545.0 + offset / 86400,
                "factor_longitudes": {
                    k: x + (0 if k == "Aries Point" else offset / 128)
                    for k, x in v.items()
                },
            }
            if definition:
                sample["angle_definition"] = deepcopy(definition)
            samples.append(sample)
        uncertainty = {
            "status": "sampled",
            "uncertainty_minutes": radius,
            "sample_count": len(samples),
            "samples": samples,
            "recorded_interval_start_utc": "synthetic-start",
            "recorded_interval_end_utc": "synthetic-end",
        }
    return layer, uncertainty


def vector(angle):
    return math.cos(math.radians(angle)), math.sin(math.radians(angle))


def rotate(v, angle):
    c, s = vector(angle)
    return c * v[0] - s * v[1], s * v[0] + c * v[1]


def four_vectors(v, axis):
    u = vector(axis)
    projection = v[0] * u[0] + v[1] * u[1]
    reflection = (2 * projection * u[0] - v[0], 2 * projection * u[1] - v[1])
    return {
        "original": v,
        "opposition": (-v[0], -v[1]),
        "solstitial_reflection": reflection,
        "reflection_opposition": (-reflection[0], -reflection[1]),
    }


def assert_angle(actual, reference):
    expected = math.degrees(math.atan2(reference[1], reference[0])) % 360
    assert abs((actual - expected + 180) % 360 - 180) < 1e-10


@pytest.mark.parametrize("aries", [0.0, 23.75, 180.0, 359.99999999999994])
def test_all_constructed_coordinates_against_independent_plane_vectors(aries):
    v = {k: (x + aries) % 360 for k, x in values().items()}
    v["Aries Point"] = aries
    geometry, _ = comparative_coordinates(v)
    groups = {
        "radix": geometry["radix_systems"],
        **{k: f["factor_systems"] for k, f in geometry["frames"].items()},
    }
    for group, rows in groups.items():
        rotation = (
            0 if group == "radix" else aries + FRAMES[group][1] - v[FRAMES[group][0]]
        )
        for name, row in rows.items():
            expected = four_vectors(rotate(vector(v[name]), rotation), aries + 90)
            for key, coordinate in row["longitudes"].items():
                assert_angle(coordinate, expected[key])
    assert set(geometry["frames"]) == set(FRAMES)


@pytest.mark.parametrize("shift", [23.5, 180.0, 359.5])
def test_display_covariance_uses_the_actual_tropical_aries_point(shift):
    v = values()
    a, _ = comparative_coordinates(v)
    b, _ = comparative_coordinates({name: (x - shift) % 360 for name, x in v.items()})
    for group in ("radix", *FRAMES):
        left = (
            a["radix_systems"]
            if group == "radix"
            else a["frames"][group]["factor_systems"]
        )
        right = (
            b["radix_systems"]
            if group == "radix"
            else b["frames"][group]["factor_systems"]
        )
        for name, row in left.items():
            for key, number in row["longitudes"].items():
                assert (
                    right[name]["longitudes"][key] - (number - shift) + 180
                ) % 360 - 180 == pytest.approx(0, abs=1e-12)
    # Applying180-lambda directly to sidereal display numbers would err by2*shift.
    shifted = {name: (x - shift) % 360 for name, x in v.items()}
    naive = (180 - shifted["Uranus"]) % 360
    correct = b["radix_systems"]["Uranus"]["longitudes"]["solstitial_reflection"]
    if shift != 180:
        assert abs((naive - correct + 180) % 360 - 180) > 0.1


@pytest.mark.parametrize(
    "longitude,unique",
    [
        (90.0, 2),
        (math.nextafter(90.0, 0), 4),
        (math.nextafter(90.0, math.inf), 4),
        (0.0, 2),
        (45.0, 4),
    ],
)
def test_unique_point_count_precedes_display_rounding(longitude, unique):
    v = values()
    v["Uranus"] = longitude
    g, _ = comparative_coordinates(v)
    row = g["radix_systems"]["Uranus"]
    assert row["unique_point_count"] == unique
    assert all(0 <= x < 360 for x in row["longitudes"].values())


@pytest.mark.parametrize(
    "definition",
    [
        {
            "status": "backend_numeric_convention_only",
            "retained_ascendant_role": "backend_numeric_convention_only",
        },
        {"status": "geographic_pole_meridian_convention"},
    ],
)
def test_unresolved_angles_and_assigned_anchor_identity_remain_distinct(definition):
    g, _ = comparative_coordinates(values(), definition)
    assert g["status"] == "partial"
    assert set(g["radix_systems"]["Ascendant"]["longitudes"].values()) == {None}
    frame = g["frames"]["ascendant_libra"]
    assert not frame["anchor_input_reference_resolved"]
    assert (
        frame["rotation_degrees"] is None
        and frame["backend_rotation_degrees"] is not None
    )
    assigned = frame["factor_systems"]["Ascendant"]
    assert (
        assigned["defined_anchor_identity"]
        and assigned["input_reference_geometry_resolved"]
    )
    assert assigned["longitudes"]["original"] == 180
    assert not frame["factor_systems"]["Sun"]["input_reference_geometry_resolved"]
    assert frame["factor_systems"]["Sun"]["backend_longitudes"] is not None


@pytest.mark.parametrize(
    "radius,expected,count",
    [(None, "not_assessed", None), (0, "sampled", 1), (0.5, "sampled", 3)],
)
def test_unknown_zero_and_confirmed_grid_are_separate_and_typed(
    radius, expected, count, monkeypatch
):
    def unexpected_query(*args, **kwargs):
        raise AssertionError("new ephemeris query")

    monkeypatch.setattr(runtime, "ephemeris_call", unexpected_query)
    layer, uncertainty = inputs(radius)
    before = deepcopy((layer, uncertainty))
    g = build_comparative_geometry(layer, uncertainty)
    assert (layer, uncertainty) == before
    s = g["birth_time_sensitivity"]
    assert s["status"] == expected and s["sample_count"] == count
    assert (
        not s["continuous_interval_proven"] and not s["sample_frequency_is_probability"]
    )
    assert (
        ComparativeGeometry.model_validate(g).model_dump(
            mode="json", exclude_unset=True
        )
        == g
    )
    if count:
        assert s["summary"]["point_systems_per_sample"] == 6 * len(values())
        assert len(s["samples"]) == count
        assert s["interval"]["recorded_interval_start_utc"] == "synthetic-start"
        assert all(
            row["resolved_sample_count"] == count
            for rows in s["point_spans"].values()
            for row in rows.values()
        )


def test_unknown_nominal_reference_does_not_turn_known_other_samples_into_a_nominal_bound():
    definition = {
        "status": "backend_numeric_convention_only",
        "retained_ascendant_role": "backend_numeric_convention_only",
    }
    layer, u = inputs(0.5, definition)
    u["samples"][0].pop("angle_definition")
    u["samples"][2].pop("angle_definition")
    g = build_comparative_geometry(layer, u)
    s = g["birth_time_sensitivity"]
    span = s["point_spans"]["radix"]["Ascendant"]
    assert s["status"] == "partial" and span["resolved_sample_count"] == 2
    assert span["unresolved_sample_indices"] == [1]
    assert span["known_sampled_signed_offsets_from_nominal"] is None
    assert span["backend_sampled_signed_offsets_from_nominal"] is not None
    # Known absolute sample coordinates remain usable even though a physical
    # offset from the unresolved nominal reference cannot be established.
    assert (
        s["samples"][0]["point_systems"]["radix"]["Ascendant"]["longitudes"]["original"]
        is not None
    )
    assert (
        s["samples"][1]["point_systems"]["radix"]["Ascendant"]["longitudes"]["original"]
        is None
    )
    assert (
        s["samples"][1]["point_systems"]["radix"]["Ascendant"]["backend_longitudes"]
        is not None
    )


@pytest.mark.parametrize(
    "change",
    [
        "count",
        "duplicate",
        "reorder",
        "missing_factor",
        "zero_tt",
        "zero_value",
        "zero_definition",
        "missing_epoch",
    ],
)
def test_corrupted_same_run_grid_is_a_typed_source_failure(change):
    layer, u = inputs(0.5)
    if change == "count":
        u["sample_count"] = True
    if change == "duplicate":
        u["samples"][2]["offset_seconds"] = 0
    if change == "reorder":
        u["samples"].reverse()
    if change == "missing_factor":
        del u["samples"][0]["factor_longitudes"]["Uranus"]
    if change == "zero_tt":
        u["samples"][1]["julian_day_tt"] += 1
    if change == "zero_value":
        u["samples"][1]["factor_longitudes"]["Uranus"] += 1
    if change == "zero_definition":
        u["samples"][1]["angle_definition"] = {
            "status": "geographic_pole_meridian_convention"
        }
    if change == "missing_epoch":
        del u["samples"][0]["julian_day_tt"]
    with pytest.raises(EphemerisSourceError) as caught:
        build_comparative_geometry(layer, u)
    result = caught.value.as_result()
    assert result["status_code"] == 503 and not result["retryable"]
    assert result["issues"][0]["code"] == "comparative_geometry_inputs"


def test_unavailable_backend_has_no_invented_coordinates():
    result = build_comparative_geometry(
        {"status": "unavailable", "reason": "synthetic unavailable"},
        {"status": "unavailable", "uncertainty_minutes": 0},
    )
    assert result["frames"] is None and result["profile"] is None
    assert result["birth_time_sensitivity"]["sample_count"] is None
    ComparativeGeometry.model_validate(result)


def source_auditor():
    spec = importlib.util.spec_from_file_location(
        "comparative_source_audit", ROOT / "scripts/western/audit_witte_comparative.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_original_rows_remain_and_four_discrepancies_cannot_be_erased():
    audit = source_auditor().audit()
    assert audit["printed_rotation_rows"] == 36 and audit["compatible_rows"] == 32
    failed = {
        (r["frame"], r["factor"]): r["printed_minus_calculated_arcminutes"]
        for r in audit["uncoordinated_rows"]
    }
    assert failed == {
        ("sun_capricorn", "Midheaven"): 8990,
        ("sun_capricorn", "Neptune"): -8,
        ("meridian_cancer", "Neptune"): -8,
        ("ascendant_libra", "Neptune"): -8,
    }
    assert audit["mirror_example"]["printed_reflection_matches"]
    assert audit["mirror_example"]["printed_reflection_of_opposition_matches"]
    assert (
        not audit["original_method_fully_accepted"] and not audit["authority_certified"]
    )


def test_modified_source_fixture_cannot_become_a_replacement_oracle(tmp_path):
    changed = json.loads(FIXTURE.read_text())
    changed["natal_table_page138"]["Neptune"] = [0, 19, 9]
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="digest mismatch"):
        source_auditor().audit(path)


@pytest.mark.native_engine_fault
def test_corrupted_nominal_epoch_is_reported_as_runtime_source_inconsistency(
    monkeypatch,
):
    from fatebridge.core.astro import sensitivity
    from fatebridge.services.astrology import calculate_germany_chart_analysis

    original = sensitivity.build_comparative_geometry

    def corrupt(layer, uncertainty):
        changed = deepcopy(uncertainty)
        zero = next(row for row in changed["samples"] if row["offset_seconds"] == 0)
        zero["julian_day_tt"] += 1
        return original(layer, changed)

    monkeypatch.setattr(sensitivity, "build_comparative_geometry", corrupt)
    result = calculate_germany_chart_analysis(
        name="虚构：比较坐标来源故障核验",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=10.0,
        birth_latitude=20.0,
        birth_time_uncertainty_minutes=0.5,
    )
    assert (
        result["error_code"] == "ephemeris_source_inconsistent"
        and result["status_code"] == 503
    )
    assert result["retryable"] is False
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "comparative_geometry_inputs"}
    ]
