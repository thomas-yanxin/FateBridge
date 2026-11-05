"""Frozen time-fraction and vector controls retain the difficult input rows."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import house_axes, runtime
from fatebridge.core.astro.angle_definitions import ecliptic_horizon_angle_definition
from fatebridge.core.astro.horizon_precision import horizon_geometry
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.zodiac import native_lahiri_houses
from fatebridge.core.predictive.native_chart import build_native_subject

FIXTURE = Path(__file__).parents[1] / "data/astro/placidus_semiarc"
CASES = json.loads((FIXTURE / "inputs.json").read_text())["cases"]
PUBLIC = json.loads((FIXTURE / "public-boundary-inputs.json").read_text())["cases"]


def read_rows(name):
    with gzip.open(FIXTURE / name, "rt") as stream:
        return {r["id"]: r for r in map(json.loads, stream)}


SEMIARC = read_rows("reference.jsonl.gz")
HORIZON = read_rows("horizon-reference.jsonl.gz")
SPATIAL = read_rows("spatial-cusp-reference.jsonl.gz")


def separation(first, second):
    return abs((first - second + 180) % 360 - 180) * 3600


def test_references_and_complete_input_plan_are_frozen():
    hashes = {
        "inputs.json": "8d6700b9efdd8a5d416154805a9a2efb08f067251bbc47c2a10caa1d107655ae",
        "reference.jsonl.gz": "7eac18efb40dd03dcab3ff695a06c241255f0eafb69546f14368af542d82704b",
        "public-boundary-inputs.json": "84012103cd6997c4c9b30c5bceed414d8b76f00bd113afa3531e7743ae4dd41d",
        "horizon-reference.jsonl.gz": "68d50eddb2112579b466228b61557392272514953e049ed1fe2547fb4d534c40",
        "spatial-cusp-reference.jsonl.gz": "b62039a81dfbd3a2a165a9bbf38a1430176344bf78109d7309ff569dbd13104b",
    }
    for name, expected in hashes.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert len(CASES) == len(SEMIARC) == 692
    assert len(PUBLIC) == len(SPATIAL) == 288
    assert len(HORIZON) == 980
    assert sum(r["status"] == "defined" for r in SEMIARC.values()) == 372


def test_all980_scalar_horizon_models_match_frozen_vector_intersections():
    for case in CASES + PUBLIC:
        model = horizon_geometry(case["latitude"], case["armc"], case["obliquity"])
        expected = HORIZON[case["id"]]
        assert (
            separation(model.tropical_ascendant, float(expected["ascendant"])) <= 1
        ), case["id"]
        assert (
            separation(model.tropical_midheaven, float(expected["midheaven"])) <= 1
        ), case["id"]


def test_all692_placidus_models_keep_undefined_rows_and_validate_defined_cusps(
    monkeypatch,
):
    native_call = runtime.ephemeris_call
    defined = undefined = 0
    for case in CASES:
        expected = SEMIARC[case["id"]]
        args = (case["armc"], case["latitude"], case["obliquity"])
        if expected["status"] != "defined":
            with pytest.raises(runtime.swe.Error):
                native_call("houses_armc", *args, b"P")
            undefined += 1
            continue
        native_cusps, native_axes = native_call("houses_armc", *args, b"P")
        _, common = native_call("houses_armc", *args, b"E")

        def supplied_model(operation, *values):
            # Geometry-level injection only: no calendar/ephemeris assertion is
            # made for these synthetic ARMC/obliquity inputs.
            if operation == "houses_ex":
                assert values[3] == b"E"
                return (), common
            if operation == "deltat_ex":
                return 0.0
            if operation == "calc":
                return (case["obliquity"], 0, 0, 0, 0, 0), 0
            raise AssertionError(operation)

        with monkeypatch.context() as scope:
            scope.setattr(runtime, "ephemeris_call", supplied_model)
            cusps, axes, receipt = canonical_house_geometry(
                julian_day_ut1=0.0,
                latitude=case["latitude"],
                longitude=0.0,
                house_code=b"P",
                native_cusps=native_cusps,
                native_angles=native_axes,
            )
        assert (
            max(separation(a, b) for a, b in zip(cusps, expected["cusps"])) <= 1
        ), case["id"]
        for index in range(12):
            if index not in (0, 6):
                assert cusps[index] == native_cusps[index]
        assert separation(cusps[0], axes[0]) <= 1
        if receipt and receipt.get("eastern_direction_precision"):
            assert (
                "placidus_horizon_endpoints1_7"
                in receipt["eastern_direction_precision"]["house_cusp_scope"]
            )
            assert set(receipt["eastern_direction_precision"]["corrected_cusps"]) <= {
                1,
                7,
            }
        defined += 1
    assert (defined, undefined) == (372, 320)


CRITICAL = [
    c
    for c in PUBLIC
    if c["latitude"] < 0
    and c["margin_degrees"] == 1e-9
    and c["target_armc"] == 89.999999
]


@pytest.mark.parametrize("case", CRITICAL, ids=lambda c: c["id"])
@pytest.mark.parametrize("code", [b"E", b"V", b"W", b"P", b"R", b"C"])
@pytest.mark.parametrize("sidereal", [False, True])
def test_real_epoch_providers_preserve_frames_and_declared_house_geometry(
    case, code, sidereal
):
    if sidereal:
        result = native_lahiri_houses(
            julian_day_ut1=case["jd_ut1"],
            julian_day_tt=case["jd_tt"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            house_code=code,
        )
        asc, cusps, receipt = (
            result["ascendant"],
            result["house_cusps"],
            result["house_axis_convention"],
        )
    else:
        raw, axes = runtime.ephemeris_call(
            "houses_ex", case["jd_ut1"], case["latitude"], case["longitude"], code
        )
        cusps, axes, receipt = canonical_house_geometry(
            julian_day_ut1=case["jd_ut1"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            house_code=code,
            native_cusps=raw,
            native_angles=axes,
        )
        asc = axes[0]
    with runtime.preserve_ephemeris_path():
        _, tropical = runtime.ephemeris_call(
            "houses_ex", case["jd_ut1"], case["latitude"], case["longitude"], b"E"
        )
        _, framed = runtime.ephemeris_call(
            "houses_ex",
            case["jd_ut1"],
            case["latitude"],
            case["longitude"],
            b"E",
            runtime.swe.FLG_SIDEREAL if sidereal else 0,
        )
    offset = (tropical[1] - framed[1]) % 360
    assert separation(asc, float(HORIZON[case["id"]]["ascendant"]) - offset) <= 1
    if code in (b"P", b"R", b"C"):
        expected = (
            HORIZON[case["id"]]["placidus"]["cusps"]
            if code == b"P"
            else SPATIAL[case["id"]][code.decode()]
        )
        assert max(separation(a, b - offset) for a, b in zip(cusps, expected)) <= 1
    assert (
        receipt["eastern_direction_precision"]["maximum_physical_error_arcseconds"]
        is None
    )


@pytest.mark.parametrize("case", CRITICAL, ids=lambda c: c["id"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_predictive_placidus_subject_carries_checked_endpoints_and_conditioning(
    case, zodiac
):
    subject = build_native_subject(
        name="prescribed numerical boundary control",
        local_datetime=datetime.fromisoformat(case["utc"]),
        longitude=case["longitude"],
        latitude=case["latitude"],
        timezone_name="UTC",
        house_system="P",
        zodiac_type=zodiac,
    )
    offset = subject.calculation_basis["ayanamsha_degrees"]
    assert (
        separation(
            subject.ascendant.abs_pos, float(HORIZON[case["id"]]["ascendant"]) - offset
        )
        <= 1
    )
    assert subject.ascendant.abs_pos == subject.first_house.abs_pos
    basis = subject.calculation_basis
    assert basis["angle_definition"]["status"] == "ecliptic_horizon_ill_conditioned"
    assert (
        "placidus_horizon_endpoints1_7"
        in basis["house_axis_convention"]["eastern_direction_precision"][
            "house_cusp_scope"
        ]
    )


@pytest.mark.parametrize("latitude,armc", [(67.5, 270.0), (-67.5, 90.0)])
def test_truly_unresolved_plane_condition_keeps_its_existing_convention(
    monkeypatch, latitude, armc
):
    eps = 22.5
    _, common = runtime.ephemeris_call("houses_armc", armc, latitude, eps, b"E")

    def supplied_model(operation, *args):
        if operation == "calc":
            return (eps, 0, 0, 0, 0, 0), 0
        if operation == "deltat_ex":
            return 0.0
        raise AssertionError(operation)

    monkeypatch.setattr(runtime, "ephemeris_call", supplied_model)
    assert house_axes._precision_geometry(0.0, latitude, common) is None
    definition = ecliptic_horizon_angle_definition(
        latitude=latitude, armc=armc, obliquity=eps, angle_method="supplied_control"
    )
    assert definition["geometric_ascendant_resolved"] is False
    assert definition["retained_ascendant_role"] == "backend_numeric_convention_only"
