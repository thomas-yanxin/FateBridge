"""Frozen vector-oracle controls for polar grazing endpoint arithmetic."""

import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from mpmath import mp

from fatebridge.core.astro import runtime
from fatebridge.core.astro.ephemeris import _swisseph_angles
from fatebridge.core.astro.horizon_precision import aligned_longitude, horizon_geometry
from fatebridge.core.astro.house_axes import canonical_house_geometry
from fatebridge.core.astro.zodiac import native_lahiri_houses
from fatebridge.core.predictive.native_chart import (
    HOUSE_ATTRIBUTES,
    build_native_subject,
)
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parent / "data/astro/horizon_precision"
INPUTS = json.loads((FIXTURE / "inputs.json").read_text())
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
EXPECTED = {row["id"]: row for row in REFERENCE["cases"]}
PUBLIC = [c for c in INPUTS["cases"] if c["kind"] == "public"]


def separation(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


def test_reference_and_unfiltered_plan_are_frozen():
    assert (
        hashlib.sha256((FIXTURE / "inputs.json").read_bytes()).hexdigest()
        == "bab226fb4d588142ef94372e7de67f834f05222cb9cf0eb442ce90105abc3976"
    )
    assert (
        hashlib.sha256((FIXTURE / "reference.json").read_bytes()).hexdigest()
        == "36a9e477c1dce66d0cd893478ea4949fe98244adfaba160f601d2058cf058da9"
    )
    assert {
        kind: sum(c["kind"] == kind for c in INPUTS["cases"])
        for kind in ("armc", "public", "original")
    } == {"armc": 132, "public": 216, "original": 126}
    assert REFERENCE["tolerance_arcseconds"] == 1.0
    assert len(EXPECTED) == len(INPUTS["cases"]) == 474


@pytest.mark.parametrize("case", INPUTS["cases"], ids=lambda c: c["id"])
def test_scalar_construction_matches_independent_vector_intersections(case):
    model = horizon_geometry(case["latitude"], case["armc"], case["obliquity"])
    ref = EXPECTED[case["id"]]
    assert separation(model.tropical_ascendant, ref["ascendant"]) <= 1
    for code, phases in (
        ("R", model.regiomontanus_phases),
        ("C", model.campanus_phases),
    ):
        for phase, expected in zip(phases, ref["cusps"][code]):
            assert separation((model.tropical_midheaven + phase) % 360, expected) <= 1


@pytest.mark.parametrize("case", PUBLIC, ids=lambda c: c["id"])
@pytest.mark.parametrize("code", [b"E", b"V", b"W", b"R", b"C"])
@pytest.mark.parametrize("sidereal", [False, True])
def test_registered_house_provider_all_locations_and_frames(case, code, sidereal):
    flags = runtime.swe.FLG_SIDEREAL if sidereal else 0
    with runtime.preserve_ephemeris_path():
        runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
        if sidereal:
            result = native_lahiri_houses(
                julian_day_ut1=case["jd_ut1"],
                julian_day_tt=case["jd_tt"],
                latitude=case["latitude"],
                longitude=case["longitude"],
                house_code=code,
            )
            asc, cusps = result["ascendant"], result["house_cusps"]
            receipt = result["house_axis_convention"]
        else:
            raw, axes = runtime.ephemeris_call(
                "houses_ex",
                case["jd_ut1"],
                case["latitude"],
                case["longitude"],
                code,
                flags,
            )
            cusps, axes, receipt = canonical_house_geometry(
                julian_day_ut1=case["jd_ut1"],
                latitude=case["latitude"],
                longitude=case["longitude"],
                house_code=code,
                native_cusps=raw,
                native_angles=axes,
                flags=flags,
            )
            asc = axes[0]
        # Sidereal origin comes from native MC, never inferred from the ASC.
        _, tropical = runtime.ephemeris_call(
            "houses_ex", case["jd_ut1"], case["latitude"], case["longitude"], b"E"
        )
        _, framed = runtime.ephemeris_call(
            "houses_ex",
            case["jd_ut1"],
            case["latitude"],
            case["longitude"],
            b"E",
            flags,
        )
        offset = (tropical[1] - framed[1]) % 360
    expected = EXPECTED[case["id"]]
    assert separation(asc, (expected["ascendant"] - offset) % 360) <= 1
    if code in (b"R", b"C"):
        for actual, value in zip(cusps, expected["cusps"][code.decode()]):
            assert separation(actual, (value - offset) % 360) <= 1
    else:
        first = (
            math.floor(asc / 30) * 30
            if code == b"W"
            else asc - (15 if code == b"V" else 0)
        )
        for i, actual in enumerate(cusps):
            assert separation(actual, (first + i * 30) % 360) <= 1
    precision = receipt["eastern_direction_precision"]
    assert precision["delivered_ascendant"] == asc
    assert list(cusps) == precision["delivered_cusps"]
    assert precision["maximum_physical_error_arcseconds"] is None
    if (
        not sidereal
        and separation(case["native_ascendant"], expected["ascendant"]) <= 1
    ):
        assert asc == case["native_ascendant"]


@pytest.mark.parametrize("case", PUBLIC[::18], ids=lambda c: c["id"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("code", ["E", "V", "W", "R", "C"])
def test_predictive_subject_receipt_is_in_delivered_frame(case, zodiac, code):
    result = build_native_subject(
        name="numerical control",
        local_datetime=datetime(case["year"], 1, 1, 0, 30, tzinfo=timezone.utc),
        longitude=case["longitude"],
        latitude=case["latitude"],
        timezone_name="UTC",
        zodiac_type=zodiac,
        house_system=code,
    )
    offset = result.calculation_basis["ayanamsha_degrees"]
    assert (
        separation(
            result.ascendant.abs_pos, (EXPECTED[case["id"]]["ascendant"] - offset) % 360
        )
        <= 1
    )
    receipt = result.calculation_basis["house_axis_convention"]
    precision = receipt["eastern_direction_precision"]
    assert (
        precision["delivered_ascendant"]
        == result.ascendant.abs_pos
        == receipt["public_ascendant"]
    )
    assert precision["delivered_cusps"] == [
        getattr(result, name).abs_pos for name in HOUSE_ATTRIBUTES
    ]
    assert precision["coordinate_frame"] == (
        "sidereal_lahiri" if zodiac == "Sidereal" else "tropical"
    )


def test_context_precision_is_private_and_unresolved_sign_fails(monkeypatch):
    case = PUBLIC[0]
    before = mp.prec

    def solve(_):
        return horizon_geometry(case["latitude"], case["armc"], case["obliquity"])

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(solve, range(16)))
    assert all(r == results[0] for r in results)
    assert mp.prec == before
    import fatebridge.core.astro.horizon_precision as module

    monkeypatch.setattr(module, "WORKING_DIGITS", (10,))
    with pytest.raises(ArithmeticError):
        solve(0)


def test_ordinary_coordinates_remain_exact_without_a_precision_receipt():
    for latitude in (0.0, 51.5, -51.5, 80.0, -80.0):
        for longitude in (0.0, 121.0):
            jd = 2451544.5208333335
            _, raw = runtime.ephemeris_call("houses_ex", jd, latitude, longitude, b"E")
            result = _swisseph_angles(jd, longitude, latitude)
            assert result["ascendant"] == raw[0] and result["midheaven"] == raw[1]
            assert "house_axis_convention" not in result


def test_changed_default_service_summary_and_evidence_use_repaired_ascendant():
    case = PUBLIC[0]
    result = calculate_core_chart_analysis(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        chart_variant="chart",
        hsys=0,
    )
    receipt = result["chart_profile"]["house_axis_convention"]
    assert receipt["house_code"] == "W"
    assert (
        receipt["note_zh"] in result["summary"]
        and receipt["note_zh"] in result["snapshot_text"]
    )
    assert result["angles"]["ascendant"]["longitude"] == receipt["public_ascendant"]
    assert (
        result["houses"][0]["cusp_longitude"]
        == math.floor(receipt["public_ascendant"] / 30) * 30
    )
    assert (
        "chart_profile.house_axis_convention"
        in result["interpretation_evidence"]["social_style"]["source_paths"]
    )


def test_antipodal_repair_and_nonretained_intersection_are_distinguished():
    assert aligned_longitude(10.0, 10.0, 180.0) == (190.0, "antipodal_endpoint")
    assert aligned_longitude(10.0, 10.0, 0.0) == (10.0, "native_coordinate_retained")
    assert aligned_longitude(11.0, 10.0, 0.0) == (10.0, "high_precision_intersection")


def test_unresolved_direction_is_not_silently_replaced_by_approximate_axes(monkeypatch):
    from fatebridge.core.astro import house_axes

    def unresolved(*args, **kwargs):
        raise ArithmeticError("injected unresolved endpoint sign")

    monkeypatch.setattr(house_axes, "horizon_geometry", unresolved)
    case = PUBLIC[0]
    with pytest.raises(EphemerisSourceError) as direct:
        _swisseph_angles(case["jd_ut1"], case["longitude"], case["latitude"])
    assert direct.value.reason == "horizon_direction_precision_unavailable"
    result = calculate_core_chart_analysis(
        birth_year=case["year"],
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        chart_variant="chart",
        hsys=0,
    )
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["status_code"] == 503 and result["retryable"] is False
    assert result["issues"] == [
        {
            "path": "runtime.ephemeris_data",
            "code": "horizon_direction_precision_unavailable",
        }
    ]
    assert "angles" not in result and "houses" not in result


@pytest.mark.parametrize("fault", ["native_failure", "invalid_obliquity", "invalid_tt"])
def test_precision_model_failure_is_an_explicit_source_error(monkeypatch, fault):
    original = runtime.ephemeris_call

    def damaged(operation, *args, **kwargs):
        if operation == "deltat_ex" and fault == "invalid_tt":
            return float("nan")
        if operation == "calc" and args[1] == runtime.swe.ECL_NUT:
            if fault == "native_failure":
                raise RuntimeError("injected house-model failure")
            if fault == "invalid_obliquity":
                return (float("nan"), 0, 0, 0, 0, 0), 0
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", damaged)
    case = PUBLIC[0]
    with pytest.raises(EphemerisSourceError) as raised:
        _swisseph_angles(case["jd_ut1"], case["longitude"], case["latitude"])
    assert raised.value.reason == "horizon_direction_model_unavailable"
