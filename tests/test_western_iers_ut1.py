"""Published C04/SOFA controls, independent of candidate clock generation."""

import gzip
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
import swisseph as swe

from fatebridge.core.astro.geometry import native_lahiri_ayanamsha
from fatebridge.core.astro.iers_ut1 import active_ut1, c04_table, use_ut1_source
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import (
    datetime_from_tt,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.output_western import WesternEventClockConversion
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroHoraryRequest,
)
from fatebridge.core.western_event_clock import build_event_subject
from fatebridge.services.western_election import calculate_election

FIXTURE = Path(__file__).parent / "fixtures/western-iers-c04-v1"
MANIFEST = json.loads((FIXTURE / "manifest.json").read_text())
ANCHORS = json.loads(gzip.decompress((FIXTURE / "anchors.json.gz").read_bytes()))
OLD_CONTROLS = json.loads(gzip.decompress((FIXTURE / "controls.json.gz").read_bytes()))
CORRECTED = FIXTURE.with_name("western-iers-c04-v2")
CORRECTION_MANIFEST = json.loads((CORRECTED / "manifest.json").read_text())
CONTROLS = json.loads(gzip.decompress((CORRECTED / "controls.json.gz").read_bytes()))
LINE = MANIFEST["tolerance_seconds"]
GEOMETRY_PATH = CORRECTED / "geometry.json"
GEOMETRY = json.loads(GEOMETRY_PATH.read_text())


def test_external_reference_and_full_source_are_sealed():
    assert MANIFEST["production_imports"] is MANIFEST["swiss_imports"] is False
    assert MANIFEST["published_daily_records"] == 23638
    for name, digest in MANIFEST["assets"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert len(ANCHORS) == 23638 and len(CONTROLS) == 22


def test_every_published_day_matches_external_sofa_clocks():
    table = c04_table()
    with use_ut1_source("iers_c04"):
        for (mjd, tt, ut1), row in zip(ANCHORS, table.samples, strict=True):
            assert mjd == row.mjd
            stamp = datetime.combine(
                datetime.fromordinal(mjd + 678576).date(),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            actual = ephemeris_time(stamp)
            assert abs(actual.jd_tt - tt) * 86400 <= LINE
            assert abs(actual.jd_ut1 - ut1) * 86400 <= LINE
            assert abs(ut1_from_tt(tt) - ut1) * 86400 <= LINE
            assert abs(tt_from_ut1(ut1) - tt) * 86400 <= LINE


@pytest.mark.parametrize("row", CONTROLS, ids=lambda r: r["utc"])
def test_declared_continuous_interpolation_preserves_all_frozen_controls(row):
    with use_ut1_source("iers_c04"):
        actual = ut1_from_tt(row["jd_tt"])
        assert abs(actual - row["jd_ut1_continuous"]) * 86400 <= LINE
        assert abs(tt_from_ut1(actual) - row["jd_tt"]) * 86400 <= LINE
        receipt = c04_table().receipt(row["jd_tt"], actual)
        assert (
            abs(receipt["ut1_minus_tai_seconds"] - row["ut1_minus_tai_seconds"]) <= LINE
        )
        assert (
            not receipt["polar_motion_applied"]
            and not receipt["celestial_pole_offsets_applied"]
            and not receipt["subdaily_tides_applied"]
        )
        assert receipt["interpolation_error_bound_seconds"] is None
        assert not receipt["absolute_accuracy_certified"]


def test_direct_astropy_historical_differences_and_endpoint_are_not_erased():
    failures = [
        r
        for r in OLD_CONTROLS
        if r["direct_astropy_difference_seconds"] is not None
        and abs(r["direct_astropy_difference_seconds"]) > LINE
    ]
    assert [r["utc"] for r in failures] == [
        "1963-10-31T12:00:00",
        "1971-12-31T12:00:00",
    ]
    assert all(abs(r["direct_astropy_difference_seconds"]) > 0.049 for r in failures)
    unavailable = [r for r in CONTROLS if r["direct_astropy_status"] < 0]
    assert [r["utc"] for r in unavailable] == ["2026-09-19T00:00:00"]
    assert unavailable[0]["jd_ut1_direct_astropy"] is None


@pytest.mark.parametrize("which", ["tt", "ut1"])
@pytest.mark.parametrize("side", [-1, 1])
def test_source_bounds_are_closed_and_never_extrapolated(which, side):
    table = c04_table()
    axis = getattr(table, which)
    fn = table.ut1_from_tt if which == "tt" else table.tt_from_ut1
    edge = axis[0] if side < 0 else axis[-1]
    assert math.isfinite(fn(edge))
    with pytest.raises(ValueError, match="no prediction, extrapolation"):
        fn(math.nextafter(edge, -math.inf if side < 0 else math.inf))


def test_utc_display_does_not_require_an_out_of_range_ut1():
    # TT from known UTC offsets is independent of an unavailable UT1 series.
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    tt = ephemeris_time(stamp).jd_tt
    with use_ut1_source("iers_c04"):
        assert abs((datetime_from_tt(tt) - stamp).total_seconds()) <= LINE
        with pytest.raises(ValueError, match="outside"):
            ephemeris_time(stamp)


def test_policy_scope_is_restored_after_errors_and_between_threads():
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
def test_invalid_time_source_is_rejected_by_shared_request(model, prefix):
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


def test_observed_source_reaches_native_rotation_without_replacing_planetary_tt():
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
    row = next(r for r in CONTROLS if r["utc"] == "2024-06-01T12:00:00")
    assert abs(actual.julian_day - row["jd_ut1_continuous"]) * 86400 <= LINE
    assert actual.julian_day_tt == old.julian_day_tt
    assert (
        actual.sun.abs_pos == old.sun.abs_pos
        and actual.moon.abs_pos == old.moon.abs_pos
    )
    assert actual.ascendant.abs_pos != old.ascendant.abs_pos
    policy = actual.calculation_basis["earth_rotation"]
    assert policy["measured_eop_applied"]
    assert policy["ut1_reference"] == receipt["ut1_reference"]
    assert policy["sidereal_time_model"] == "IERS2010_expression_Swiss_nutation"
    WesternEventClockConversion.model_validate(receipt)


def test_selected_lahiri_uses_explicit_tt_and_not_native_modeled_delta_t():
    row = next(r for r in CONTROLS if r["utc"] == "2024-06-01T12:00:00")
    with use_ut1_source("iers_c04"):
        tt = row["jd_tt"]
        u = ut1_from_tt(tt)
        actual = native_lahiri_ayanamsha(u, julian_day_tt=tt)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        _, expected = swe.get_ayanamsa_ex(tt, swe.FLG_SWIEPH)
        assert actual == expected


def test_public_failed_observed_request_does_not_leak_its_context():
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


def test_reference_correction_is_separate_and_scale_consistent():
    assert CORRECTION_MANIFEST["created_after_candidate"]
    assert CORRECTION_MANIFEST["development_reference_not_blind"]
    assert CORRECTION_MANIFEST["production_imports"] is False
    for name, sha in CORRECTION_MANIFEST["assets"].items():
        assert hashlib.sha256((CORRECTED / name).read_bytes()).hexdigest() == sha
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


def test_supplemental_geometry_reference_is_sealed_and_not_blind():
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


@pytest.mark.parametrize("row", GEOMETRY["geometry"])
def test_observed_rotation_native_axes_match_sofa_geometry(row):
    with use_ut1_source("iers_c04"):
        subject = build_native_subject(
            name="SOFA geometry",
            physical_epoch=PhysicalEpoch.from_ut1(row["jd_ut1"]),
            longitude=row["longitude"],
            latitude=row["latitude"],
            house_system="R",
            timezone_name="UTC",
        )
    for key, attr in (("ascendant", "ascendant"), ("midheaven", "medium_coeli")):
        residual = (getattr(subject, attr).abs_pos - row[key] + 180) % 360 - 180
        assert abs(residual) * 3600 <= GEOMETRY["angle_line_arcseconds"]


@pytest.mark.parametrize("row", GEOMETRY["synthetic_solar_inputs"])
def test_sofa_solar_minute_inputs_preserve_observed_leap_epoch(row):
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
