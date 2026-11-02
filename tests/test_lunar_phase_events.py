"""Modern phase geometry, bracket membership, and explicit-model failure paths."""

import math
from fractions import Fraction as F

import pytest

from fatebridge.core import lunar_phase_events as subject


@pytest.mark.parametrize("start,end", [(0, 30), (30, 60), (-30, 0)])
def test_exact_boundary_event_included_only_at_window_start(monkeypatch, start, end):
    monkeypatch.setattr(subject, "_phase", lambda t: (12 * t) % 360)
    result = subject.phase_events_tt(start, end)
    assert [r["phase_kind"] for r in result["events"]] == list(subject.KINDS)
    assert [F(r["julian_day_tt_exact"]) for r in result["events"]] == [
        F(start) + F(15, 2) * i for i in range(4)
    ]
    assert result["timescale"] == "TT"
    assert not result["utc_or_local_civil_calendar_assigned"]
    assert not result["source_profile_reconstruction"]
    assert not result["physical_accuracy_claimed_from_numerical_resolution"]


def test_wrap_crossing_and_subday_windows_do_not_skip_new_moon(monkeypatch):
    monkeypatch.setattr(subject, "_phase", lambda t: (350 + 12 * t) % 360)
    result = subject.phase_events_tt(0, 1)
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert event["phase_kind"] == "new_moon"
    assert abs(F(event["julian_day_tt_exact"]) - F(5, 6)) <= F(1, 172800000)
    assert not subject.phase_events_tt(0.1, 0.2)["events"]


@pytest.mark.parametrize(
    "window", [(0, 0), (1, 0), (0, 3661), (math.nan, 1), (0, math.inf)]
)
def test_invalid_or_unbounded_windows_rejected(window):
    with pytest.raises(ValueError):
        subject.phase_events_tt(*window)


@pytest.mark.parametrize("window", [(False, 1), (0, True), ("0", 1)])
def test_no_implicit_time_conversion_or_boolean_jd(window):
    with pytest.raises(TypeError):
        subject.phase_events_tt(*window)


@pytest.mark.parametrize(
    "fn", [lambda t: 0, lambda t: (350 - t) % 360, lambda t: 40 * t]
)
def test_daily_nonprogress_or_large_advance_is_not_silently_unwrapped(monkeypatch, fn):
    monkeypatch.setattr(subject, "_phase", fn)
    with pytest.raises(ValueError):
        subject.phase_events_tt(0, 1)


def test_actual_ephemeris_model_is_checked_for_both_luminaries(monkeypatch):
    calls = []

    def fake(op, t, body, flag):
        calls.append(body)
        return (10, 0, 0, 13 if body == subject.swe.MOON else 1), (
            subject.swe.FLG_SWIEPH
            if body == subject.swe.MOON
            else subject.swe.FLG_MOSEPH
        )

    monkeypatch.setattr(subject, "ephemeris_call", fake)
    with pytest.raises(ValueError, match="Moshier"):
        subject._phase(2451545)
    assert calls == [subject.swe.SUN, subject.swe.MOON]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_ephemeris_nonfinite_longitude_rejected(monkeypatch, bad):
    monkeypatch.setattr(
        subject, "ephemeris_call", lambda *a: ((bad, 0, 0, 1), subject.swe.FLG_MOSEPH)
    )
    with pytest.raises(ValueError, match="有限"):
        subject._phase(2451545)


def test_nonpositive_relative_speed_is_not_used_for_search(monkeypatch):
    monkeypatch.setattr(
        subject, "ephemeris_call", lambda *a: ((10, 0, 0, 1), subject.swe.FLG_MOSEPH)
    )
    with pytest.raises(ValueError, match="递增"):
        subject._phase(2451545)


def test_native_moshier_all_quarters_close_the_geometric_target():
    result = subject.phase_events_tt(2451545, 2451580)
    assert len(result["events"]) in (4, 5)
    assert set(r["phase_kind"] for r in result["events"]) == set(subject.KINDS)
    for row in result["events"]:
        at = float(F(row["julian_day_tt_exact"]))
        difference = (
            subject._phase(at) - row["target_elongation_degrees"] + 180
        ) % 360 - 180
        # Numerical root/rounding check; independent reference accuracy tested separately.
        assert abs(difference) < 1e-6
