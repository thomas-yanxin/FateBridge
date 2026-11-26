"""Complete schedule, actual selected source and no silent source substitution."""

import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from fatebridge.core import almanac, de440_solar
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.contracts.output_canping_solar import CanpingInterval
from fatebridge.core.contracts.output_chinese import CanpingSeries, CanpingTiming
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.numerology import canping_solar
from fatebridge.core.numerology.canping_solar import (
    projection_boundary,
    resolve_projection_boundary,
)
from fatebridge.core.numerology.canping_timing import (
    APPENDIX,
    CONTINUOUS,
    resolve_annual_series,
)
from fatebridge.utils.civil_time import CivilPoint, utc_calendar
from fatebridge.utils.errors import EphemerisSourceError

INPUT = dict(
    date="2200-05-15",
    time="09:00",
    timezone="UTC",
    gender="男",
    use_true_solar_time=False,
)


@pytest.mark.parametrize("mode", ["de440", "analytic", "auto"])
@pytest.mark.parametrize("method", [APPENDIX, CONTINUOUS])
def test_complete_120_years_and_query_use_same_selected_model(
    monkeypatch: MonkeyPatch, mode: str, method
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    result = build_canping_result(
        **INPUT, dayun_method=method, analysis_datetime="2319-06-01T12:00:00Z"
    )
    series, timing = result["liunian_series"], result["canping_timing"]
    rows, boundaries, context = (
        series["rows"],
        series["year_boundaries"],
        series["solar_context"],
    )
    assert len(rows) == 120 and len(boundaries) == 121
    assert [r["year"] for r in rows] == list(range(2200, 2320))
    assert [b["year"] for b in boundaries] == list(range(2200, 2321))
    assert context["derived_event_years"] == list(range(2201, 2321))
    assert context == timing["solar_year_context"]
    assert context["public_model_years_extended"] is False
    expected = (
        "fatebridge_analytic_solar_v1"
        if mode == "analytic"
        else de440_solar.CANPING_MODEL_ID
    )
    assert {b["record"]["ephemeris_model"] for b in boundaries[1:]} == {expected}
    for i, row in enumerate(rows):
        assert row["segments"][0]["start_at"] == row["start_at"]
        assert row["segments"][-1]["end_at"] == row["end_at"]
        assert row["end_at"] == boundaries[i + 1]["record"]["datetime_with_offset"]
        if i:
            assert rows[i - 1]["end_at"] == row["start_at"]
        else:
            pass
    selected = timing["selected"]
    assert selected["year"] == 2319 and selected["ganzhi"] == rows[-1]["ganzhi"]
    assert selected["year_start_boundary"] == boundaries[-2]
    assert selected["year_end_boundary"] == boundaries[-1]
    assert selected["dayun_index"] != 0
    assert CanpingSeries.model_validate(series).model_dump(exclude_unset=True) == series
    assert CanpingTiming.model_validate(timing).model_dump(exclude_unset=True) == timing


@pytest.mark.parametrize("mode", ["de440", "analytic"])
@pytest.mark.parametrize(
    "date,zone,origin", [("1800-01-01", "+14:00", 1799), ("2200-01-01", "-12:00", 2199)]
)
def test_january_endpoints_use_local_civil_origin_without_clipping(
    monkeypatch: MonkeyPatch, mode: str, date: str, zone: str, origin: int
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    result = build_canping_result(**{**INPUT, "date": date, "timezone": zone})
    series = result["liunian_series"]
    assert series["birth_pillar_year"] == origin
    assert len(series["rows"]) == 120 and len(series["year_boundaries"]) == 121
    assert series["year_boundaries"][0]["year"] == origin
    assert series["rows"][0]["start_at"].startswith(date)


def test_future_lichun_uses_retained_point_and_outside_horizon_is_rejected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    first = build_canping_result(**INPUT)["liunian_series"]
    at = datetime.fromisoformat(first["year_boundaries"][-2]["instant_utc"])
    point = first["year_boundaries"][-2]["record"]["civil_point"]
    exact = Fraction(int(point["numerator"]), int(point["denominator"]))
    # A rounded display label is not generally the retained endpoint itself.
    for shift in (-1, 0, 1):
        query = at + timedelta(microseconds=shift)
        selected = build_canping_result(**INPUT, analysis_datetime=query.isoformat())[
            "canping_timing"
        ]["selected"]
        assert selected["year"] == (
            2318 if utc_calendar(query).julian_day_exact() < exact else 2319
        )
    with pytest.raises(ValueError, match="超出本次年序"):
        build_canping_result(
            **INPUT,
            analysis_datetime=(
                datetime.fromisoformat(first["year_boundaries"][-1]["instant_utc"])
                + timedelta(microseconds=1)
            ).isoformat(),
        )
    with pytest.raises(ValueError, match="早于出生"):
        build_canping_result(**INPUT, analysis_datetime="2200-01-01T00:00:00Z")


@pytest.mark.parametrize("shift,expected_year", [(-1, 2000), (0, 2000), (1, 2001)])
def test_frozen_2001_lichun_query_keeps_original_two_part_point(
    shift, expected_year: int, monkeypatch: MonkeyPatch
) -> None:
    """Frozen21 candidate rule chose2001 first, before any source edit.

    Independent ERFA2.0.1 UTC->TAI->TT and exact DAT32s/TT−TAI32.184s
    place the accepted display label0.169914876us before this unchanged root.
    This is propagation evidence, not physical submicrosecond accuracy.
    """
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    expected_tt = Fraction(1380321913017060365667, 562949953421312)
    event = resolve_projection_boundary(
        2001, "UTC", origin_civil_year=2000, origin_bazi_year=2000, horizon=120
    )
    assert event.term.tt_instant.days == expected_tt
    assert event.term.point.day == expected_tt - Fraction(8023, 125) / 86400
    at = datetime(2001, 2, 3, 18, 28, 49, 643537, tzinfo=timezone.utc)
    query = at + timedelta(microseconds=shift)
    result = build_canping_result(
        date="2000-05-15",
        time="09:00",
        timezone="UTC",
        gender="男",
        use_true_solar_time=False,
        analysis_datetime=query.isoformat(),
    )
    selected = result["canping_timing"]["selected"]
    assert selected["year"] == expected_year
    start, end = (
        Fraction(int(selected[k]["numerator"]), int(selected[k]["denominator"]))
        for k in ("start_point", "end_point")
    )
    assert start <= utc_calendar(query).julian_day_exact() < end


def test_real_lichun_and_civil_cut_may_share_display_without_collapsing_interval(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    birth = datetime(2000, 5, 15, 9, tzinfo=timezone.utc)
    # Synthetic SDK period at a civil-label point, not an asserted horoscope.
    period = {
        "index": 0,
        "branch": "子",
        "pillar": "甲子",
        "start_at": "2001-02-03T18:28:49.643537+00:00",
        "end_at": "2121-01-01T00:00:00+00:00",
    }
    series = resolve_annual_series(birth, "UTC", [period], "金", horizon=2)
    interval = next(
        i for i in series.intervals if i.year == 2000 and i.facts["status"] == "active"
    )
    assert interval.start.day < interval.end.day
    assert interval.start_label.isoformat() == interval.end_label.isoformat()
    assert interval.year_end_boundary.year == 2001
    assert interval.end is interval.year_end_boundary.term.point
    CanpingSeries.model_validate(series.record, context={"full_result": True})


def test_exact_interval_contract_accepts_same_label_and_rejects_nonpositive_points() -> (
    None
):
    label = "2001-02-03T12:00:00+00:00"
    day = utc_calendar(datetime.fromisoformat(label)).julian_day_exact()
    quarter_microsecond = Fraction(1, 345600000000)
    start = CivilPoint(day - quarter_microsecond).to_record()
    end = CivilPoint(day + quarter_microsecond).to_record()
    complete = {
        "start_at": label,
        "end_at": label,
        "start_point": start,
        "end_point": end,
        "comparison_policy": "retained_nominal_civil_point_v1",
    }
    CanpingInterval.model_validate(complete, context={"full_result": True})
    for left, right in ((start, start), (end, start)):
        with pytest.raises(ValidationError, match="正长度半开区间"):
            CanpingInterval.model_validate(
                {**complete, "start_point": left, "end_point": right}
            )
    incomplete = {key: value for key, value in complete.items() if key != "end_point"}
    CanpingInterval.model_validate(incomplete)
    with pytest.raises(ValidationError, match="完整数值端点"):
        CanpingInterval.model_validate(incomplete, context={"full_result": True})


def test_projected_interval_cap_is_unknown_until_explicitly_supplied() -> None:
    cap = utc_calendar(datetime(2017, 1, 1, tzinfo=timezone.utc)).julian_day_exact()
    start = CivilPoint(cap - Fraction(1, 864000000000), cap).to_record()
    complete = {
        "start_at": "2016-12-31T23:59:59.999999+00:00",
        "end_at": "2017-01-01T00:00:00+00:00",
        "start_point": start,
        "end_point": CivilPoint(cap).to_record(),
        "comparison_policy": "retained_nominal_civil_point_v1",
    }
    CanpingInterval.model_validate(complete, context={"full_result": True})
    projected_start = {
        key: value for key, value in start.items() if key != "excluded_before"
    }
    partial = CanpingInterval.model_validate(
        {**complete, "start_point": projected_start}
    )
    assert partial.start_point.known_day() == cap - Fraction(1, 864000000000)
    assert partial.start_point.known_point() is None
    with pytest.raises(ValidationError, match="数值端点与显示标签不一致"):
        CanpingInterval.model_validate(
            {**complete, "start_point": {**start, "excluded_before": None}}
        )


@pytest.mark.parametrize("year,horizon", [(2321, 120), (2320, 119), (2201, True)])
def test_derived_event_permission_remains_bounded(
    year: int, horizon: bool | int
) -> None:
    with pytest.raises(ValueError):
        projection_boundary(
            year, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=horizon
        )


@pytest.mark.parametrize("mode", ["de440", "analytic"])
def test_public_year_grid_is_not_extended(monkeypatch: MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    # The original2320 rejection is retained. Only the explicit DE440
    # contract's reported range changed; R68's old regex failure is archived.
    message = "1700..2300" if mode == "de440" else "1800..2200"
    with pytest.raises(ValueError, match=message):
        almanac.get_solar_terms_for_year(2320, "UTC")


def test_missing_derived_profile_fails_without_switching_model(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.setitem(
        de440_solar.PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    de440_solar._profile.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError):
            projection_boundary(
                2201, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
            )
    finally:
        de440_solar._profile.cache_clear()


def test_explicit_analytic_never_loads_de440_projection_profile(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.setitem(
        de440_solar.PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    row = projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    assert row["record"]["ephemeris_model"] == "fatebridge_analytic_solar_v1"


def test_unused_projection_profile_is_not_a_birth_year_dependency(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.setitem(
        de440_solar.PROFILE_FILES,
        de440_solar.CANPING_MODEL_ID,
        "missing-canping-source",
    )
    row = projection_boundary(
        2001, "UTC", origin_civil_year=2000, origin_bazi_year=2000, horizon=120
    )
    assert row["selection"] == "ordinary_public_year_grid"
    assert row["record"]["ephemeris_model"] == de440_solar.MODEL_ID


def test_source_configuration_change_is_rejected_and_cached_receipts_are_copied(
    monkeypatch: MonkeyPatch,
) -> None:

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    args = dict(origin_civil_year=2200, origin_bazi_year=2200, horizon=120)
    first = projection_boundary(2201, "UTC", **args)
    first["record"]["solar_model_details"]["model_id"] = "forged"
    second = projection_boundary(2201, "UTC", **args)
    assert (
        second["record"]["solar_model_details"]["model_id"]
        == de440_solar.CANPING_MODEL_ID
    )
    original = canping_solar._root

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
        return result

    monkeypatch.setattr(canping_solar, "_root", changed)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        projection_boundary(2201, "UTC", **args)


def test_loaded_projection_manifest_identity_rejects_relabelled_scope(
    monkeypatch: MonkeyPatch,
) -> None:
    original = de440_solar.files

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def joinpath(self, name):
            return Entry(self.entry.joinpath(name))

        def read_bytes(self):
            raw = self.entry.read_bytes()
            if self.entry.name == "de440-solar-canping-v1.json":
                return b"{invalid"
            else:
                pass
            return raw

    monkeypatch.setattr(de440_solar, "files", lambda package: Entry(original(package)))
    de440_solar._profile.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError):
            de440_solar.source_receipt(de440_solar.CANPING_MODEL_ID)
    finally:
        de440_solar._profile.cache_clear()


def test_receipt_contract_rejects_changed_instant_and_clipped_count() -> None:
    with pytest.raises(ValidationError):
        CanpingSeries.model_validate(
            {"solar_context": {"horizon_years": 120, "boundary_count": 120}}
        )
    with pytest.raises(ValidationError):
        CanpingTiming.model_validate(
            {
                "selected": {
                    "year_start_boundary": {
                        "instant_utc": "2300-02-04T00:00:00Z",
                        "record": {"datetime_with_offset": "2300-02-05T00:00:00Z"},
                    }
                }
            }
        )
