"""Full independent reference cohort, timescale separation and boundary roots."""

import hashlib
import json
import math
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_modern_time as modern
from fatebridge.validation import guolao_modern_solstices as audit

FIXTURES = Path(__file__).parents[1] / "fixtures/guolao-modern-solstices-v1"
SOURCE = json.loads(audit.DATA.read_bytes())
QUERIES = sorted(FIXTURES.glob("*.query.json"))
COMPLETE = [p for p in QUERIES if p.name != "coarse.query.json"]


def test_cli_zero_denominator_is_parameter_error_without_success_payload(
    monkeypatch, capsys
):
    script = (
        Path(__file__).parents[2] / "scripts/guolao/audit_guolao_modern_solstices.py"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "clock",
            "--year",
            "1900",
            "--tt-jd",
            "1/0",
            "--tdb-minus-ut1-seconds",
            "100",
            "--apparent-solar-hours",
            "0",
            "--longitude-east-degrees",
            "0",
            "--policy",
            modern.CLOCK_POLICY,
        ],
    )
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script))["main"]()
    assert error.value.code == 2
    assert not capsys.readouterr().out


@pytest.mark.parametrize("query", COMPLETE, ids=lambda p: p.stem)
def test_every_complete_raw_response_preserves_all_requested_times_and_declared_frame(
    query,
):
    params = json.loads(query.read_bytes())
    name = query.name.removesuffix(".query.json")
    result = audit.parse_horizons_observer(
        (FIXTURES / (name + ".response.json")).read_bytes(),
        [F(v) for v in params["requested_tt_jds_exact"]],
        clock=name == "historical-clocks",
        inertial=name == "frame-diagnostic",
    )
    assert len(result["rows"]) == len(params["requested_tt_jds_exact"])
    assert "JDTT" in result["header"]
    assert result["signature"] == {"source": "NASA/JPL Horizons API", "version": "1.0"}


def test_initial_truncated80_rows_are_rejected_as_reference_not_salvaged():
    query = json.loads((FIXTURES / "coarse.query.json").read_bytes())
    assert len(query["requested_tt_jds_exact"]) == 294
    with pytest.raises(ValueError, match="不完整"):
        audit.parse_horizons_observer(
            (FIXTURES / "coarse.response.json").read_bytes(),
            [F(v) for v in query["requested_tt_jds_exact"]],
            clock=False,
        )


@pytest.mark.parametrize(
    "case", SOURCE["reference_brackets"], ids=lambda row: row["case"]["id"]
)
def test_full_fixed_window_native_root_and_subsecond_external_bracket_both_retained(
    case,
):
    from datetime import date

    row = case["case"]
    start = (
        date(row["year"], row["gregorian_month"], row["start_day"]).toordinal()
        + 1721424.5
    )
    result = modern.solar_crossing_tt(row["target_deg"], start, start + 5)
    low, high = map(F, result["bracket_tt_jd_exact"])
    reslow, reshigh = map(F, result["bracket_residual_degrees_exact"])
    assert reslow <= 0 <= reshigh
    assert F(result["selected_jd_tt_exact"]) == high
    assert F(result["bracket_width_seconds_exact"]) < F(1, 1000)
    assert F(case["upper_tt_jd_exact"]) - F(case["lower_tt_jd_exact"]) == F(1, 131072)
    # The independent root is not substituted for a native root merely to match it.
    assert result["window_tt_jd"] == [start, start + 5]
    assert not result["numerical_resolution_is_physical_accuracy"]
    assert not result["UTC_or_historical_local_clock_assigned"]


@pytest.mark.parametrize(
    "row", SOURCE["historical_clock_rows"], ids=lambda row: row["case_id"]
)
def test_each_historical_clock_separates_time_scale_longitude_and_equation_of_time(row):
    parts = modern.historical_clock_components(
        F(row["tt_jd_exact"]),
        F(row["TDB_minus_UT1_seconds"]),
        F(row["apparent_solar_hours"]),
        F("116.4"),
        year=row["year"],
        timescale_difference_policy=modern.CLOCK_POLICY,
    )
    assert F(parts["meridian_day_correction_exact"]) == F(97, 300)
    assert (
        F(parts["apparent_local_calendar_label_serial_exact"]) % 1
        == F(row["apparent_solar_hours"]) / 24
    )
    assert not parts["source_midnight_and_clock_policy_calibrated"]
    assert not parts["UTC_assigned"]


def test_clock_sign_units_and_year_policy_with_a_constructed_UT1_midnight():
    tt = F("2415020.5") + F(100, 86400)
    row = modern.historical_clock_components(
        tt,
        F(100),
        F("0.1"),
        F(0),
        year=1900,
        timescale_difference_policy=modern.CLOCK_POLICY,
    )
    assert F(row["approximate_ut1_jd_exact"]) == F("2415020.5")
    assert F(row["mean_local_calendar_label_serial_exact"]) == 2415021
    assert F(row["equation_of_time_seconds_exact"]) == 360
    with pytest.raises(ValueError, match="伪报"):
        modern.historical_clock_components(
            F(2451545),
            F(64),
            F(12),
            F(0),
            year=1900,
            timescale_difference_policy=modern.CLOCK_POLICY,
        )


@pytest.mark.parametrize("year", [1962, 2000, 2026, True, "1280", 0])
def test_post1962_TDB_UTC_and_invalid_years_cannot_be_misused_as_UT1(year):
    with pytest.raises(ValueError):
        modern.historical_clock_components(
            F(2451545),
            F(64),
            F(12),
            F("116.4"),
            year=year,
            timescale_difference_policy=modern.CLOCK_POLICY,
        )


def _fake_native(monkeypatch, *, speed=1, flag=None):
    def calc(operation, jd, body, flags):
        assert operation == "calc"
        longitude = float((F(jd) - 100) % 360)
        if longitude == 360:
            longitude = math.nextafter(360, 0)
        return (longitude, 0, 1, speed, 0, 0), (
            flag if flag is not None else modern.swe.FLG_MOSEPH | modern.swe.FLG_SPEED
        )

    monkeypatch.setattr(modern, "ephemeris_call", calc)


def test_zero_degree_wrap_start_inclusion_end_exclusion_and_opposite_direction_guard(
    monkeypatch,
):
    _fake_native(monkeypatch)
    crossing = modern.solar_crossing_tt(0, 99, 101)
    assert F(crossing["selected_jd_tt_exact"]) == 100
    at_start = modern.solar_crossing_tt(0, 100, 101)
    assert at_start["bracket_tt_jd_exact"] == ["100", "100"]
    with pytest.raises(ValueError, match="唯一"):
        modern.solar_crossing_tt(0, 99, 100)
    with pytest.raises(ValueError, match="唯一"):
        modern.solar_crossing_tt(180, 99, 101)


@pytest.mark.parametrize("speed", [0, -1, float("nan"), float("inf")])
def test_bad_solar_motion_is_rejected_instead_of_becoming_a_root(monkeypatch, speed):
    _fake_native(monkeypatch, speed=speed)
    with pytest.raises(ValueError, match="无效"):
        modern.solar_crossing_tt(0, 99, 101)


def test_backend_switch_or_fallback_is_not_accepted(monkeypatch):
    _fake_native(monkeypatch, flag=modern.swe.FLG_SWIEPH | modern.swe.FLG_SPEED)
    with pytest.raises(ValueError, match="Moshier"):
        modern.solar_crossing_tt(0, 99, 101)


@pytest.mark.parametrize(
    "args",
    [
        (True, 99, 101),
        (0, "99", 101),
        (0, 100, 100),
        (360, 99, 101),
        (0, 99, 132),
        (0, float("nan"), 101),
    ],
)
def test_invalid_TT_targets_or_windows_have_no_implicit_defaults(args):
    with pytest.raises((TypeError, ValueError)):
        modern.solar_crossing_tt(*args)


def test_all_frozen_source_requests_and_postcomparison_diagnostic_hashes():
    initial = json.loads((FIXTURES / "reference.json").read_bytes())
    later = json.loads((FIXTURES / "postcomparison-frame-reference.json").read_bytes())
    assert initial["data_sha256"] == hashlib.sha256(audit.DATA.read_bytes()).hexdigest()
    assert (
        later["data_sha256"]
        == hashlib.sha256(
            audit.DATA.with_name(
                "modern-solstices-frame-diagnostic-v1.json"
            ).read_bytes()
        ).hexdigest()
    )
    for reference in (initial, later):
        for artifact in reference["artifacts"]:
            raw = (FIXTURES / artifact["path"]).read_bytes()
            assert len(raw) == artifact["bytes"]
            assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    assert not initial["reference_collector_imported_fatebridge"]
    assert later["postcomparison_diagnostic"]
    assert later["diagnostic_reference_not_unseen_holdout"]


def test_complete_audit_does_not_select_source_typo_or_clock_by_smallest_modern_error():
    result = audit.audit_modern_solstices()
    assert len(result["all14_fixed_window_modern_events"]) == 14
    assert len(result["all12_historical_clock_comparisons"]) == 12
    winter = next(
        v
        for v in result["all12_historical_clock_comparisons"]
        if v["case_id"] == "winter1280"
    )
    assert len(winter["source_comparisons"]) == 3
    profiles = {v["source_profile"] for v in winter["source_comparisons"]}
    assert "fixed_original_qiying_55_06" in profiles
    assert all(
        not v["best_clock_hypothesis_or_source_variant_selected_by_error"]
        for v in winter["source_comparisons"]
    )
    assert len(result["postcomparison_frame_diagnostic"]["records"]) == 14
    assert not result["full_original_calendar_or_local_clock_calibrated"]
    assert not result["four_axis_perfect_scores_established"]


def test_optional_DE441_common_frame_diagnostic_requires_actual_files_and_retains_default_date_difference():
    result = audit.audit_frame_diagnostic(include_swieph=True)
    assert len(result["records"]) == 28
    for row in result["records"]:
        assert row["inertial_state"]["frame"] == "apparent_equatorial_icrf"
        assert row["tropical_state"]["frame"] == "native_apparent_tropical_date"
        assert not row["date_frames_reconciled_or_native_policy_changed"]
        assert math.isfinite(row["inertial_tangent_distance_arcseconds"])
        if row["inertial_state"]["backend"] == "swieph_de441":
            assert len(row["inertial_state"]["observed_source_files"]) == 2
            assert all(
                v["jpl_denum"] == 441
                for v in row["inertial_state"]["observed_source_files"]
            )
