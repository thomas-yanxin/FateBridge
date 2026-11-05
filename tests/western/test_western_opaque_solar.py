"""Independent Horizons controls for an explicit opaque-Sun position layer.

Native transparent-Sun disagreement remains failed under its original gate.
The alternative changes a declared ray policy, never a reference or tolerance.
"""

import csv
import hashlib
import io
import json
import math
import os
from datetime import datetime
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.core.astro import opaque_solar
from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.time_scales import ut1_from_tt
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.utils.errors import EphemerisSourceError
from scripts.western.audit_western_reference_points import audit_opaque_solar_positions
from tests.support.transports import SPECS, business, native, rest, surface_calls

DATA = Path(__file__).parents[1] / "data/astro/mercury-opaque-solar"
ORIGINAL = (
    Path(__file__).parents[1] / "fixtures/western-event-reference-points-horizons.json"
)
ORIGINAL_SHA = "6cffd8c638538212dac6248b97c8432b149dd7e512c86c4d92942c9a7fe44aba"


def source_rows(stem):
    path = DATA / f"{stem}-response.json"
    binding = json.loads((DATA / "provenance.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["files"][path.name]
    text = json.loads(path.read_text())["result"]
    return text, list(
        csv.reader(io.StringIO(text.split("$$SOE\n")[1].split("$$EOE")[0].strip()))
    )


def unit(ra, dec):
    ra, dec = math.radians(ra), math.radians(dec)
    return math.cos(ra) * math.cos(dec), math.sin(ra) * math.cos(dec), math.sin(dec)


def separation(a, b):
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(x * y for x, y in zip(a, b)))
        )
        * 3600
    )


@pytest.mark.local_data
def test_original_7070_pairs_all_frames_keep_original_tolerance_and_reference():
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA
    result = audit_opaque_solar_positions()
    assert result["body_epoch_pairs"] == result["expected_body_epoch_pairs"] == 7070
    assert result["frame_comparisons"] == 14140
    assert result["original_tolerance_arcseconds"] == 0.02
    assert result["passed"] and result["failures"] == []
    assert result["solar_disc_intercepted_body_epoch_pairs"] > 0
    assert not result["native_mismatch_overridden"]
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == ORIGINAL_SHA


@pytest.mark.local_data
def test_original_native_transparent_sun_mismatch_is_not_relabelled_as_pass():
    corpus = json.loads(ORIGINAL.read_text())
    row = corpus["cases"][1]["rows"]["Mercury"][477]
    tt = row["julian_day_tt"]
    assert tt == 2459892.375
    expected = row["projections"][opaque_solar.FRAME]
    state, model = _swisseph_planet_state(
        "Mercury", ut1_from_tt(tt), julian_day_tt=tt, correct_motion=False
    )
    old_error = abs(state["longitude"] - expected[0]) * 3600
    assert model == "swieph" and 0.89 < old_error < 0.90
    assert old_error > 0.02
    actual = opaque_solar.opaque_solar_positions(tt, ["Mercury"])
    position = actual["positions"][0]
    assert (
        position["solar_disc_intercepted"] and not position["solar_deflection_applied"]
    )
    assert abs(position["longitude"] - expected[0]) * 3600 <= 0.02
    assert abs(position["latitude"] - expected[1]) * 3600 <= 0.02
    assert not actual["natal_chart_recomputed"]


@pytest.mark.local_data
def test_paired_jpl_observer_and_lt_stellar_raw_prove_opaque_policy_without_production():
    observer_header, observer = source_rows("mercury-opacity")
    vector_header, vectors = source_rows("mercury-lt-stellar-vector")
    solar_header, solar = source_rows("sun-radius")
    assert "Date__(TT)" in observer_header and "JDTT" in vector_header
    assert "LT+S CORRECTED" in vector_header and "DE441" in observer_header
    assert "695700.0" in solar_header
    assert len(observer) == len(vectors) == 9
    inside = outside = 0
    for row, vector in zip(observer, vectors, strict=True):
        assert row[0].strip().replace(".000", ".0000") in vector[1]
        apparent = unit(float(row[11]), float(row[12]))
        xyz = tuple(map(float, vector[2:5]))
        norm = math.hypot(*xyz)
        residual = separation(apparent, [x / norm for x in xyz])
        if row[4].strip() == "o":
            inside += 1
            # JPL's own two outputs agree to printed-coordinate rounding.
            assert residual < 0.00001
            assert float(row[3]) < float(solar[0][3]) / 2
        else:
            outside += 1
            assert row[4].strip() == "*" and 0.28 < residual < 0.48
            assert float(row[3]) > float(solar[0][3]) / 2
    assert (inside, outside) == (5, 4)


@pytest.mark.local_data
def test_nine_additional_horizons_visibility_controls_keep_full_exterior_deflection():
    _, observer = source_rows("mercury-opacity")
    _, vectors = source_rows("mercury-lt-stellar-vector")
    for row, vector in zip(observer, vectors, strict=True):
        # Civil text is a TT label; parsing it avoids the shortened 9-decimal
        # JD printed in the separate vector table. No TT/TDB substitution.
        label = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        tt = 2440587.5 + (label - datetime(1970, 1, 1)).total_seconds() / 86400
        actual = opaque_solar.opaque_solar_positions(tt, ["Mercury"])["positions"][0]
        assert (
            separation(
                actual["apparent_icrs_unit_direction"],
                unit(float(row[11]), float(row[12])),
            )
            <= 0.02
        )
        assert actual["solar_disc_intercepted"] == (row[4].strip() == "o")
        assert actual["solar_deflection_applied"] == (row[4].strip() == "*")
        if actual["solar_deflection_applied"]:
            xyz = tuple(map(float, vector[2:5]))
            norm = math.hypot(*xyz)
            # Turning GR off everywhere fails these exterior controls.
            assert (
                separation(
                    actual["apparent_icrs_unit_direction"], [x / norm for x in xyz]
                )
                > 0.28
            )


@pytest.mark.local_data
def test_nine_offgrid_horizons_holdout_epochs_keep_original_numerical_line():
    _, observer = source_rows("mercury-offgrid-holdout")
    corpus = json.loads(ORIGINAL.read_text())
    original_epochs = {
        row["julian_day_tt"]
        for case in corpus["cases"]
        for row in case["rows"]["Mercury"]
    }
    assert len(observer) == 9
    for row in observer:
        label = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        tt = 2440587.5 + (label - datetime(1970, 1, 1)).total_seconds() / 86400
        assert tt not in original_epochs
        position = opaque_solar.opaque_solar_positions(tt, ["Mercury"])["positions"][0]
        assert (
            separation(
                position["apparent_icrs_unit_direction"],
                unit(float(row[11]), float(row[12])),
            )
            <= 0.02
        )
        assert position["solar_disc_intercepted"] == (row[4].strip() == "o")


@pytest.mark.parametrize(
    "height",
    [
        math.nextafter(float(opaque_solar.SOLAR_RADIUS_AU), -math.inf),
        float(opaque_solar.SOLAR_RADIUS_AU),
        math.nextafter(float(opaque_solar.SOLAR_RADIUS_AU), math.inf),
    ],
)
def test_limb_geometry_uses_exact_supplied_values_without_epsilon(height):
    with localcontext() as context:
        context.prec = 100
        radius = Decimal(695700000) / Decimal(149597870700)
        expected = Decimal(height) ** 2 < radius**2
    assert (
        opaque_solar.opaque_solar_intersection(
            [1.0, height, 0.0], [-1.0, height, 0.0], [0.0, 0.0, 0.0]
        )
        == expected
    )


def test_finite_ray_does_not_occult_a_foreground_target_or_a_sun_behind_observer():
    assert opaque_solar.opaque_solar_intersection(
        [1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    )
    assert not opaque_solar.opaque_solar_intersection(
        [1.0, 0.0, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 0.0]
    )
    assert not opaque_solar.opaque_solar_intersection(
        [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    )


@pytest.mark.parametrize(
    "observation", [0.0, -12345.0, 2451545.0, 2460398.8333333335, 1e8]
)
def test_stationary_source_selects_exact_rational_first_post_light_cone(observation):
    # The constant one-AU source gives an independent exact root. These are
    # mathematical TT carriers, not claimed observed dates or source accuracy.
    exact = Fraction(observation) - Fraction(149597870700, 299792458 * 86400)
    expected = float(exact)
    if Fraction(expected) < exact:
        expected = math.nextafter(expected, math.inf)
    solved, count, proof = opaque_solar._retarded_state(
        observation, [0.0, 0.0, 0.0], lambda at: ((1.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0)
    )
    assert solved.epoch == expected
    assert Fraction(proof["lower_jd_tt"]) < exact <= Fraction(proof["upper_jd_tt"])
    assert math.nextafter(proof["lower_jd_tt"], math.inf) == proof["upper_jd_tt"]
    assert proof["lower_residual_seconds"] < 0 < proof["upper_residual_seconds"]
    assert 1 <= count <= 20


def test_subluminal_linear_source_has_certified_adjacent_root_not_cycle_acceptance():
    observation = 2460398.8333333335
    lower = observation - 0.01
    upper = math.nextafter(lower, math.inf)
    midpoint = (Fraction(lower) + Fraction(upper)) / 2
    c = Fraction(299792458 * 86400, 149597870700)
    velocity = c / 100

    def source(at):
        # Independent linear trajectory whose unrounded root is the midpoint.
        distance = float(
            c * (Fraction(observation) - midpoint)
            + velocity * (Fraction(at) - midpoint)
        )
        return (distance, 0.0, 0.0, float(velocity), 0.0, 0.0), 0

    solved, count, proof = opaque_solar._retarded_state(
        observation, [0.0, 0.0, 0.0], source
    )
    assert solved.epoch == upper
    assert proof["lower_jd_tt"] == lower and proof["upper_jd_tt"] == upper
    with localcontext() as context:
        context.prec = 100
        speed = Decimal(299792458) * Decimal(86400) / Decimal(149597870700)
        for epoch, sign in [(lower, -1), (upper, 1)]:
            values, _ = source(epoch)
            residual = (
                Decimal(epoch) - Decimal(observation) + Decimal(values[0]) / speed
            ) * Decimal(86400)
            assert residual * sign > 0
    assert 1 <= count <= 20


def test_exact_light_cone_root_is_distinguished_from_an_adjacent_bracket():
    solved, count, proof = opaque_solar._retarded_state(
        2451545.0, [0.0, 0.0, 0.0], lambda at: ((0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0)
    )
    assert solved.epoch == 2451545.0 and count == 1
    assert proof["exact_root"] and proof["bracket_width_seconds"] == 0
    assert proof["lower_residual_seconds"] == proof["upper_residual_seconds"] == 0


def test_unbracketed_source_still_fails_after_the_original_twenty_steps():
    observation = 2451545.0
    calls = []

    def no_light_cone(at):
        # A numerical source violating the subluminal prerequisite: F stays
        # positive. Its endless proposals must never become a computed place.
        calls.append(at)
        return (
            opaque_solar.LIGHT_SPEED_AU_DAY * (observation - at) + 1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ), 0

    with pytest.raises(EphemerisSourceError) as failure:
        opaque_solar._retarded_state(observation, [0.0, 0.0, 0.0], no_light_cone)
    assert failure.value.reason == "opaque_solar_light_time_not_stabilized"
    assert len(calls) == 20


@pytest.mark.local_data
def test_real_retarded_bracket_satisfies_independent_decimal_light_cone():
    actual = opaque_solar.opaque_solar_positions(2460398.8333333335, ["Venus"])
    position = actual["positions"][0]
    proof = position["light_time_solution"]
    lower, upper = proof["lower_jd_tt"], proof["upper_jd_tt"]
    assert math.nextafter(lower, math.inf) == upper
    assert position["emission_jd_tt"] == upper
    earth = actual["earth_barycentric_icrs_au_au_day"]
    with localcontext() as context:
        context.prec = 100
        c = Decimal(299792458) * Decimal(86400) / Decimal(149597870700)
        for epoch, source, key, sign in [
            (
                lower,
                proof["lower_target_barycentric_icrs_au_au_day"],
                "lower_residual_seconds",
                -1,
            ),
            (
                upper,
                position["target_barycentric_icrs_au_au_day"],
                "upper_residual_seconds",
                1,
            ),
        ]:
            distance = sum(
                (Decimal(source[i]) - Decimal(earth[i])) ** 2 for i in range(3)
            ).sqrt()
            residual = (
                Decimal(epoch) - Decimal(actual["jd_tt"]) + distance / c
            ) * Decimal(86400)
            assert residual * sign > 0
            assert abs(float(residual) - proof[key]) < 1e-12


def test_named_model_rejects_unavailable_barycentric_source_without_native_fallback(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    with pytest.raises(EphemerisSourceError):
        opaque_solar.opaque_solar_positions(2459892.375, ["Mercury"])


@pytest.mark.parametrize("flag", ["FLG_ICRS", "FLG_SPEED"])
@pytest.mark.local_data
def test_coordinate_contract_fault_remains_explicit(flag, monkeypatch):
    original = opaque_solar.runtime.ephemeris_call

    def fault(*args, **kwargs):
        result, flags = original(*args, **kwargs)
        return result, flags & ~getattr(opaque_solar.runtime.swe, flag)

    monkeypatch.setattr(opaque_solar.runtime, "ephemeris_call", fault)
    with pytest.raises(EphemerisSourceError):
        opaque_solar.opaque_solar_positions(2459892.375, ["Mercury"])


PAYLOAD = dict(
    birth_year=2022,
    birth_month=11,
    birth_day=8,
    birth_hour=21,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=0.0,
    birth_latitude=40.0,
    hsys=0,
    zodiacal=0,
    ephemeris_policy="require_data_files",
)


def test_missing_optional_erfa_is_a_clear_503_on_actual_transports(
    monkeypatch, tmp_path, surface_calls
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setattr(opaque_solar, "find_spec", lambda name: None)
    spec = SPECS["astro_chart"]
    request = {**PAYLOAD, "ephemeris_policy": "auto", "apparent_model": "opaque_solar"}
    response, protocol, code, cli = surface_calls(spec, request, cli_first=False)
    assert response.status_code == 503 and protocol.is_error and code != 0
    for result in [response.json(), protocol.structured_content, cli]:
        assert result["error_code"] == "dependency_missing"
        assert "apparent_model_positions" not in result


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.local_data
def test_default_native_chart_remains_identical_and_new_layer_is_not_mixed_into_aspects(
    zodiacal,
):
    payload = {**PAYLOAD, "zodiacal": zodiacal}
    default = calculate_core_chart_analysis(**payload)
    explicit = calculate_core_chart_analysis(**payload, apparent_model="native")
    selected = calculate_core_chart_analysis(**payload, apparent_model="opaque_solar")
    layer = selected.pop("apparent_model_positions")
    assert default == explicit == selected
    assert len(layer["positions"]) == 10
    assert set(row["body"] for row in layer["positions"]) == set(
        opaque_solar.PHYSICAL_BODIES
    )
    assert (
        layer["scope"] == "standalone_positions_only"
        and not layer["natal_chart_recomputed"]
    )
    assert (
        layer["frame"] == opaque_solar.FRAME
        and layer["physical_ephemeris_source"]["has_unidentified_sources"] is False
    )


@pytest.mark.local_data
def test_explicit_model_and_schema_on_actual_rest_fastmcp_and_cli(surface_calls):
    spec = SPECS["astro_chart"]
    request = {**PAYLOAD, "apparent_model": "opaque_solar"}
    fields = ["apparent_model_positions", "planets", "chart_profile.julian_day_tt"]
    response, protocol, code, cli = surface_calls(
        spec,
        request,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields, "--strict-fields", "--no-include-snapshot-text"],
        cli_first=False,
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    result = business(response.json())
    assert result == business(protocol.structured_content) == business(cli)
    layer = result["apparent_model_positions"]
    assert len(layer["positions"]) == 10 and not layer["natal_chart_recomputed"]
    selected_file = os.environ.get("FATEBRIDGE_JPL_FILE")
    expected_model = "jpl" if selected_file else "swieph"
    source = layer["physical_ephemeris_source"]
    assert {entry["model"] for entry in source["by_factor"].values()} == {
        expected_model
    }
    if selected_file:
        assert [entry["filename"] for entry in source["files"]] == [selected_file]
    expected_flag = 1 if selected_file else 2
    assert all(
        flag & 7 == expected_flag
        for row in layer["positions"]
        for flag in row["input_state_return_flags"]
    )
    assert layer["jd_tt"] == result["chart_profile"]["julian_day_tt"]
    mercury = next(row for row in layer["positions"] if row["body"] == "Mercury")
    assert mercury["solar_disc_intercepted"] and not mercury["solar_deflection_applied"]
    spec.output_model.model_validate(result)
    Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    mercury["latitude"] = 91.0
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(result)


@pytest.mark.parametrize(
    "extra",
    [
        {"apparent_model": "opqaue_solar"},
        {"apparent_model": "opaque_solar", "chart_variant": "chart13"},
    ],
)
def test_invalid_selector_or_unsupported_variant_is_rejected_all_transports(
    extra, surface_calls
):
    spec = SPECS["astro_chart"]
    request = {**PAYLOAD, **extra}
    response, protocol, code, cli = surface_calls(spec, request, cli_first=False)
    assert response.status_code == 422 and protocol.is_error and code != 0
