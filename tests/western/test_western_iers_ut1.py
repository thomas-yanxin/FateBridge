"""Published C04/SOFA controls, independent of candidate clock generation."""

import gzip
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

import pytest
import swisseph as swe

from fatebridge.core.astro.earth_attitude import physical_equator
from fatebridge.core.astro.geometry import native_lahiri_ayanamsha
from fatebridge.core.astro.iers_ut1 import active_ut1, c04_table, use_ut1_source
from fatebridge.core.astro.terrestrial_observer import (
    terrestrial_frame,
    terrestrial_observer,
)
from fatebridge.core.astro.time_scales import (
    datetime_from_tt,
    ephemeris_time,
    ut1_from_tt,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.core.contracts.output_western import WesternEventClockConversion
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.core.western_event_clock import build_event_subject
from fatebridge.services.western_election import calculate_election
from tests.support.reference_data import verify_source_files

FIXTURE = Path(__file__).parents[1] / "data/astro/iers_c04"
MANIFEST = json.loads((FIXTURE / "reference-info.json").read_text())
ANCHORS = json.loads(gzip.decompress((FIXTURE / "anchors.json.gz").read_bytes()))
CORRECTED = FIXTURE
CONTROLS = json.loads(gzip.decompress((CORRECTED / "controls.json.gz").read_bytes()))
LINE = MANIFEST["tolerance_seconds"]
GEOMETRY_PATH = CORRECTED / "geometry.json"
GEOMETRY = json.loads(GEOMETRY_PATH.read_text())

MODERN_PROVENANCE = json.loads((FIXTURE / "modern-eop-v1.provenance.json").read_text())


def _modern_fixture(name):
    raw = (FIXTURE / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MODERN_PROVENANCE["files"][name]
    return json.loads(gzip.decompress(raw))


MODERN_MATH = _modern_fixture("modern-eop-math-v1.json.gz")
MODERN_GEOMETRY = _modern_fixture("modern-sofa-geometry-v1.json.gz")


def _worst_interval_error(actual, reference, scale=1):
    point = F(actual)
    return (
        max(
            abs(point - F(reference["lower"])),
            abs(point - F(reference["upper"])),
        )
        * scale
    )


def _reference_float(reference):
    return float.fromhex(reference["hex"])


def test_receipt_reports_the_supplied_tt_ut1_pair_within_agreement_tolerance() -> None:
    table = c04_table()
    tt = TTInstant(F("2460463.123456789"))
    solved = table.evaluate(tt)
    supplied = UT1Instant(solved.ut1 + F(150, 86400 * 10**6))

    receipt = table.receipt(tt, supplied)

    delta_t = (tt.days - supplied.days) * 86400
    assert receipt["delta_t_seconds"] == float(delta_t)
    assert receipt["ut1_minus_tai_seconds"] == float(F("32.184") - delta_t)
    assert receipt["solver_residual_seconds"] == pytest.approx(150e-6, abs=1e-9)


def test_published_c04_samples_match_sealed_sofa_and_flint_source_anchors() -> None:
    raw = (FIXTURE / "flint-interpolation-v1.json.gz").read_bytes()
    proof = json.loads((FIXTURE / "flint-interpolation-v1.provenance.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == proof["reference_sha256"]
    reference = json.loads(gzip.decompress(raw))
    table = c04_table()
    gate = F(str(LINE))
    for sample, flint, sofa in zip(
        table.samples, reference["anchors"], ANCHORS, strict=True
    ):
        assert sample.mjd == flint["mjd"] == sofa[0]
        assert abs(sample.tt.days - F(flint["tt_exact"])) * 86400 <= gate
        assert abs(sample.ut1 - F(flint["ut1_exact"])) * 86400 <= gate
        assert abs(sample.tt.as_float() - sofa[1]) * 86400 <= LINE
        assert abs(float(sample.ut1) - sofa[2]) * 86400 <= LINE


def test_external_reference_and_full_source_are_sealed() -> None:
    assert MANIFEST["production_imports"] is MANIFEST["swiss_imports"] is False
    assert MANIFEST["published_daily_records"] == 23638
    verify_source_files(FIXTURE)
    assert len(ANCHORS) == 23638 and len(CONTROLS) == 22


def test_direct_astropy_historical_differences_and_endpoint_are_not_erased() -> None:
    failures = [
        r
        for r in CONTROLS
        if r["direct_astropy_difference_seconds"] is not None
        and abs(r["direct_astropy_difference_seconds"]) > LINE
    ]
    assert [r["utc"] for r in failures] == [
        "1962-08-01T12:00:00",
        "1963-10-31T12:00:00",
        "1963-11-01T12:00:00",
        "1964-04-01T12:00:00",
        "1971-12-31T12:00:00",
    ]
    large = [r for r in failures if abs(r["direct_astropy_difference_seconds"]) > 0.049]
    assert [r["utc"] for r in large] == ["1963-10-31T12:00:00", "1971-12-31T12:00:00"]
    unavailable = [r for r in CONTROLS if r["direct_astropy_status"] < 0]
    assert [r["utc"] for r in unavailable] == ["2026-09-19T00:00:00"]
    assert unavailable[0]["jd_ut1_direct_astropy"] is None


@pytest.mark.parametrize("which", ["tt", "ut1"])
@pytest.mark.parametrize("side", [-1, 1])
def test_source_bounds_are_closed_and_never_extrapolated(which: str, side) -> None:
    table = c04_table()
    axis = table.tt if which == "tt" else table.ut1_bounds
    fn = table.ut1_from_tt if which == "tt" else table.tt_from_ut1
    edge = axis[0] if side < 0 else axis[-1]
    if which == "tt":
        assert math.isfinite(fn(TTInstant(edge)))
    else:
        assert math.isfinite(fn(edge).as_float())
    with pytest.raises(ValueError, match="outside"):
        fn(math.nextafter(float(edge), -math.inf if side < 0 else math.inf))


def test_utc_display_does_not_require_an_out_of_range_ut1() -> None:
    # TT from known UTC offsets is independent of an unavailable UT1 series.
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    tt = ephemeris_time(stamp).jd_tt
    with use_ut1_source("iers_c04"):
        assert abs((datetime_from_tt(tt) - stamp).total_seconds()) <= LINE
        with pytest.raises(ValueError, match="outside"):
            ephemeris_time(stamp)


def test_policy_scope_is_restored_after_errors_and_between_threads() -> None:
    stamp = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)
    expected = ephemeris_time(stamp)
    with pytest.raises(ValueError):
        with use_ut1_source("iers_c04"):
            ut1_from_tt(0)
    assert active_ut1.get() is None and ephemeris_time(stamp) == expected

    def at(source):
        with use_ut1_source(source):
            return ephemeris_time(stamp)

    with ThreadPoolExecutor(max_workers=2) as pool:
        modeled, observed = list(pool.map(at, ["swiss_delta_t", "iers_c04"]))
    assert modeled == expected and modeled.jd_tt == observed.jd_tt
    assert modeled.jd_ut1 != observed.jd_ut1 and active_ut1.get() is None


@pytest.mark.parametrize(
    "model,prefix",
    [(AstroElectionRequest, "candidate"), (AstroHoraryRequest, "question")],
)
def test_invalid_time_source_is_rejected_by_shared_request(model, prefix: str) -> None:
    with pytest.raises(ValueError):
        model.model_validate(
            {
                prefix + "_year": 2024,
                prefix + "_month": 1,
                prefix + "_day": 1,
                prefix + "_hour": 0,
                "longitude": 0,
                "latitude": 40,
                "ut1_source": "auto_observed",
            }
        )


def test_observed_source_reaches_native_rotation_without_replacing_planetary_tt() -> (
    None
):
    args = dict(
        name="published UT1 comparison",
        local_datetime=datetime(2024, 6, 1, 12),
        longitude=0,
        latitude=40,
        timezone_name="UTC",
    )
    with use_ut1_source("swiss_delta_t"):
        old, _ = build_event_subject(**args)
    with use_ut1_source("iers_c04"):
        actual, receipt = build_event_subject(**args)
    row = next(r for r in MODERN_MATH["cases"] if r["id"] == "M02")
    assert actual.julian_day == float.fromhex(row["forward"]["inverse_given_IEEE_hex"])
    assert actual.julian_day_tt == old.julian_day_tt
    assert (
        actual.sun.abs_pos == old.sun.abs_pos
        and actual.moon.abs_pos == old.moon.abs_pos
    )
    assert actual.ascendant.abs_pos != old.ascendant.abs_pos
    policy = actual.calculation_basis["earth_rotation"]
    assert policy["measured_eop_applied"]
    assert policy["ut1_reference"] == receipt["ut1_reference"]
    assert policy["policy_id"] == "fatebridge_physical_earth_attitude_v7_c04"
    assert policy["sidereal_time_model"] == (
        "IAU2006_2000A_model_EO_with_C04_CIP_and_polar_motion"
    )
    orientation = policy["terrestrial_orientation"]
    assert orientation["polar_motion_applied"]
    assert orientation["celestial_pole_offsets_applied"]
    assert orientation["cio_locator_policy"] == "retain_IAU2006_model_s_before_CPO"
    for value, key in zip(
        orientation["celestial_pole_offsets_arcseconds"],
        ["daily_dX_arcsec", "daily_dY_arcsec"],
        strict=True,
    ):
        assert _worst_interval_error(value, row["forward"]["components"][key]) <= F(
            "1e-10"
        )
    assert receipt["ut1_reference"]["subdaily_tides_applied"]
    assert not receipt["ut1_reference"]["polar_motion_applied"]
    assert not receipt["ut1_reference"]["celestial_pole_offsets_applied"]
    WesternEventClockConversion.model_validate(receipt)


def test_selected_lahiri_uses_explicit_tt_and_not_native_modeled_delta_t() -> None:
    row = next(r for r in CONTROLS if r["utc"] == "2024-06-01T12:00:00")
    with use_ut1_source("iers_c04"):
        tt = row["jd_tt"]
        u = ut1_from_tt(tt)
        actual = native_lahiri_ayanamsha(u, julian_day_tt=tt)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        _, expected = swe.get_ayanamsa_ex(tt, swe.FLG_SWIEPH)
        assert actual == expected


def test_public_failed_observed_request_does_not_leak_its_context() -> None:
    value = calculate_election(
        candidate_year=1646,
        candidate_month=1,
        candidate_day=1,
        candidate_hour=0,
        longitude=0,
        latitude=40,
        ut1_source="iers_c04",
    )
    assert "error" in value and active_ut1.get() is None


def test_reference_correction_is_separate_and_scale_consistent() -> None:
    assert MANIFEST["development_reference_not_blind"]
    verify_source_files(FIXTURE)
    changed = [r for r in CONTROLS if abs(r["reference_correction_seconds"]) > LINE]
    assert len(changed) == 5
    for row in CONTROLS:
        expected = row["jd_tt"] + (row["ut1_minus_tai_seconds"] - 32.184) / 86400
        assert abs(expected - row["jd_ut1_continuous"]) * 86400 <= LINE
    assert (
        len(
            [
                r
                for r in CONTROLS
                if r["direct_astropy_difference_seconds"] is not None
                and abs(r["direct_astropy_difference_seconds"]) > LINE
            ]
        )
        == 5
    )


def test_supplemental_geometry_reference_is_sealed_and_not_blind() -> None:
    assert (
        hashlib.sha256(GEOMETRY_PATH.read_bytes()).hexdigest()
        == "767bb3d7ebcb57d4621dd57af1d78d171fbef5fdef83a66214364bf351259d9f"
    )
    assert (
        GEOMETRY["created_after_candidate"]
        and GEOMETRY["development_reference_not_blind"]
    )
    assert GEOMETRY["production_imports"] is False
    assert GEOMETRY["angle_line_arcseconds"] == 0.02
    assert GEOMETRY["clock_line_seconds"] == LINE


@pytest.mark.parametrize("row", GEOMETRY["synthetic_solar_inputs"])
def test_sofa_solar_minute_inputs_preserve_observed_leap_epoch(row) -> None:
    with use_ut1_source("iers_c04"):
        subject, receipt = build_event_subject(
            name="SOFA leap minute",
            local_datetime=datetime.fromisoformat(row["wall"]),
            longitude=row["longitude"],
            latitude=40,
            clock_basis=row["basis"],
        )
    assert abs(subject.julian_day_tt - row["jd_tt"]) * 86400 <= LINE
    assert abs(subject.julian_day - row["jd_ut1"]) * 86400 <= LINE
    assert receipt["converted_utc"].startswith("2016-12-31T23:59:60.")


@pytest.mark.parametrize("row", MODERN_MATH["cases"], ids=lambda row: row["id"])
def test_modern_c04_matches_independent_interval_clock_and_orientation(row) -> None:
    table = c04_table()
    forward, inverse = row["forward"], row["inverse"]
    tt = TTInstant(F(forward["TT_given"]))
    given_ut1 = UT1Instant(F(forward["inverse_given_IEEE_UT1"]))
    actual = table.evaluate(tt)
    assert _worst_interval_error(actual.ut1, forward["UT1_interval"], 86400) <= F(
        "1e-11"
    )
    assert _worst_interval_error(
        actual.zonal_ut1_seconds, forward["components"]["zonal_seconds"]
    ) <= F("1e-11")
    if inverse["expected_source_error"]:
        with pytest.raises(ValueError, match="outside"):
            table.tt_from_ut1(given_ut1)
    else:
        inverted = table.tt_from_ut1(given_ut1)
        assert _worst_interval_error(inverted.days, inverse["TT_interval"], 86400) <= F(
            "1e-11"
        )
    orientation = table.orientation(tt, given_ut1)
    assert _worst_interval_error(
        orientation.x_arcsec, forward["components"]["full_x_arcsec"]
    ) <= F("1e-10")
    assert _worst_interval_error(
        orientation.y_arcsec, forward["components"]["full_y_arcsec"]
    ) <= F("1e-10")
    assert orientation.cpo_arcsec is not None
    for value, key in zip(
        orientation.cpo_arcsec, ["daily_dX_arcsec", "daily_dY_arcsec"], strict=True
    ):
        assert _worst_interval_error(value, forward["components"][key]) <= F("1e-10")


@pytest.mark.parametrize(
    "row", MODERN_GEOMETRY["sites"], ids=lambda row: row["reference"]["id"]
)
def test_c04_physical_triad_receiver_and_enu_match_original_sofa(row) -> None:
    reference = row["reference"]
    context = MODERN_GEOMETRY["contexts"][row["context_id"]]
    tt = TTInstant(F(context["TT_parts"]["given_representative_days"]))
    given_ut1 = UT1Instant(F(context["UT1_parts"]["given_representative_days"]))
    site = reference["site_given"]
    longitude = float(site["longitude_degrees"])
    latitude = float(site["latitude_degrees"])
    with use_ut1_source("iers_c04"):
        equator = physical_equator(swe, given_ut1, julian_day_tt=tt)
        receiver = terrestrial_observer(
            equator,
            longitude=longitude,
            latitude=latitude,
            height=float(site["height_metres"]),
        )
        frame = terrestrial_frame(equator, longitude=longitude, latitude=latitude)
    for actual_row, expected_row in zip(
        equator.matrix, context["N_corrected"], strict=True
    ):
        for value, expected in zip(actual_row, expected_row, strict=True):
            assert abs(F(value) - F(_reference_float(expected))) <= F("5e-13")
    for value, expected in zip(
        receiver.position, reference["PV_GCRS_CIO"][0], strict=True
    ):
        assert abs(F(value) * 149_597_870_700 - F(_reference_float(expected))) <= F(
            "1e-5"
        )
    for value, expected in zip(
        receiver.velocity, reference["PV_GCRS_CIO"][1], strict=True
    ):
        assert abs(
            F(value) * F(149_597_870_700, 86400) - F(_reference_float(expected))
        ) <= F("1e-9")
    for name, axis in [("east", frame.east), ("north", frame.north), ("up", frame.up)]:
        actual = tuple(
            math.fsum(axis[k] * equator.matrix[k][j] for k in range(3))
            for j in range(3)
        )
        for value, expected in zip(actual, reference["ENU_GCRS"][name], strict=True):
            assert abs(F(value) - F(_reference_float(expected))) <= F("5e-13")
