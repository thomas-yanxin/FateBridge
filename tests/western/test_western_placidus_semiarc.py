"""Frozen time-fraction and vector controls retain the difficult input rows."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astro import house_axes, runtime
from fatebridge.core.astro.angle_definitions import ecliptic_horizon_angle_definition
from fatebridge.core.astro.horizon_precision import horizon_geometry
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.zodiac import native_lahiri_houses
from fatebridge.core.predictive.native_chart import (
    HOUSE_ATTRIBUTES,
    build_native_subject,
)

FIXTURE = Path(__file__).parents[1] / "data/astro/placidus_semiarc"
CURRENT_FRAME_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures/western-placidus-current-frame-reference-v1.json"
)
CASES = json.loads((FIXTURE / "inputs.json").read_text())["cases"]
PUBLIC = json.loads((FIXTURE / "public-boundary-inputs.json").read_text())["cases"]
CURRENT_FRAME = json.loads(CURRENT_FRAME_FIXTURE.read_text())["cases"]


def read_rows(name):
    with gzip.open(FIXTURE / name, "rt") as stream:
        return {r["id"]: r for r in map(json.loads, stream)}


SEMIARC = read_rows("reference.jsonl.gz")
HORIZON = read_rows("horizon-reference.jsonl.gz")
SPATIAL = read_rows("spatial-cusp-reference.jsonl.gz")


def separation(first, second):
    return abs((first - second + 180) % 360 - 180) * 3600


def assert_cusps_match(cusps, expected):
    assert max(separation(a, b) for a, b in zip(cusps, expected, strict=True)) <= 1


def supply_house_obliquity(monkeypatch, obliquity):
    def supplied_attitude(_module, _ut1, *, julian_day_tt=None):
        return SimpleNamespace(
            equator=SimpleNamespace(jd_tt=0.0),
            reduction=SimpleNamespace(
                house_obliquity=obliquity,
                house_longitude_origin=0.0,
            ),
        )

    monkeypatch.setattr(house_axes, "earth_attitude", supplied_attitude)


def test_references_and_complete_input_plan_are_frozen() -> None:
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
    assert (
        hashlib.sha256(CURRENT_FRAME_FIXTURE.read_bytes()).hexdigest()
        == "2fff9d38bd46b11d57f9fac8aeb82457532025a51d41f7014c4a8ecaab427010"
    )


def test_all980_scalar_horizon_models_match_frozen_vector_intersections() -> None:
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        else:
            pass
        native_cusps, native_axes = native_call("houses_armc", *args, b"P")
        _, common = native_call("houses_armc", *args, b"E")

        def supplied_model(operation, *values, _julian_day_tt):
            assert operation == "houses_ex" and values[3] == b"E"
            return (), common

        with monkeypatch.context() as scope:
            scope.setattr(runtime, "ephemeris_call", supplied_model)
            supply_house_obliquity(scope, case["obliquity"])
            cusps, axes, receipt = canonical_house_geometry(
                julian_day_ut1=0.0,
                latitude=case["latitude"],
                longitude=0.0,
                house_code=b"P",
                native_cusps=native_cusps,
                native_angles=native_axes,
            )
        assert (
            max(separation(a, b) for a, b in zip(cusps, expected["cusps"], strict=True))
            <= 1
        ), case["id"]
        for index in range(12):
            if index not in (0, 6):
                assert cusps[index] == native_cusps[index]
            else:
                pass
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
        else:
            pass
        defined += 1
    assert (defined, undefined) == (372, 320)


CRITICAL = [
    c
    for c in PUBLIC
    if c["latitude"] < 0
    and c["margin_degrees"] == 1e-9
    and c["target_armc"] == 89.999999
]


def real_epoch_geometry(case, code, sidereal):
    if sidereal:
        result = native_lahiri_houses(
            julian_day_ut1=case["jd_ut1"],
            julian_day_tt=case["jd_tt"],
            latitude=case["latitude"],
            longitude=case["longitude"],
            house_code=code,
        )
        return (
            result["ascendant"],
            result["midheaven"],
            result["house_cusps"],
            result["house_axis_convention"],
        )
    else:
        pass
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
    return axes[0], axes[1], cusps, receipt


@pytest.mark.parametrize("case", CRITICAL, ids=lambda c: c["id"])
@pytest.mark.parametrize("code", [b"E", b"V", b"W", b"P", b"R", b"C"])
@pytest.mark.parametrize("sidereal", [False, True])
def test_real_epoch_providers_preserve_frames_and_declared_house_geometry(
    case, code: bytes, sidereal: bool
) -> None:
    frame = CURRENT_FRAME[case["id"]]["frozen_tt" if sidereal else "implicit_tt"]
    expected_cusps = frame["cusps"][code.decode()]
    if expected_cusps is None:
        with pytest.raises(runtime.swe.Error):
            real_epoch_geometry(case, code, sidereal)
        return
    else:
        pass

    asc, mc, cusps, receipt = real_epoch_geometry(case, code, sidereal)
    assert separation(asc, frame["ascendant"]) <= 1
    assert separation(mc, frame["midheaven"]) <= 1
    assert_cusps_match(cusps, expected_cusps)
    assert (
        receipt["eastern_direction_precision"]["maximum_physical_error_arcseconds"]
        is None
    )


@pytest.mark.parametrize("case", CRITICAL, ids=lambda c: c["id"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_predictive_placidus_subject_carries_checked_endpoints_and_conditioning(
    case, zodiac: str
) -> None:
    kwargs = dict(
        name="prescribed numerical boundary control",
        local_datetime=datetime.fromisoformat(case["utc"]),
        longitude=case["longitude"],
        latitude=case["latitude"],
        timezone_name="UTC",
        house_system="P",
        zodiac_type=zodiac,
    )
    frame = CURRENT_FRAME[case["id"]]["civil"][zodiac]
    expected_cusps = frame["cusps"]["P"]
    if expected_cusps is None:
        with pytest.raises(
            ValueError, match="Cannot compute P houses.*no substitute house system"
        ) as refusal:
            build_native_subject(**kwargs)
        assert isinstance(refusal.value.__cause__, runtime.swe.Error)
        return
    else:
        pass

    subject = build_native_subject(**kwargs)
    assert separation(subject.ascendant.abs_pos, frame["ascendant"]) <= 1
    assert separation(subject.medium_coeli.abs_pos, frame["midheaven"]) <= 1
    assert_cusps_match(
        (subject.points[name].abs_pos for name in HOUSE_ATTRIBUTES), expected_cusps
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
    monkeypatch: pytest.MonkeyPatch, latitude, armc: float
) -> None:
    eps = 22.5
    _, common = runtime.ephemeris_call("houses_armc", armc, latitude, eps, b"E")

    supply_house_obliquity(monkeypatch, eps)
    assert house_axes._precision_geometry(0.0, latitude, common, longitude=0) is None
    definition = ecliptic_horizon_angle_definition(
        latitude=latitude, armc=armc, obliquity=eps, angle_method="supplied_control"
    )
    assert definition["geometric_ascendant_resolved"] is False
    assert definition["retained_ascendant_role"] == "backend_numeric_convention_only"
