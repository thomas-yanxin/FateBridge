"""Canping Lichun boundary resolution, compact series, and audit budget tests."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from fatebridge.core import almanac
from fatebridge.core.contracts.numerology import (
    CanpingInterval,
    CanpingSeries,
    CanpingTiming,
)
from fatebridge.core.numerology import solar
from fatebridge.core.numerology.canping_result import build_canping_result
from fatebridge.core.numerology.solar import (
    projection_boundary,
    resolve_projection_boundary,
)
from fatebridge.core.numerology.timing import APPENDIX, CONTINUOUS
from fatebridge.utils.civil_time import CivilPoint, utc_calendar

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
    monkeypatch: MonkeyPatch, mode: str, method: str
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    result = build_canping_result(
        **INPUT, dayun_method=method, analysis_datetime="2319-06-01T12:00:00Z"
    )
    series, timing = result["liunian_series"], result["canping_timing"]
    rows, context = series["rows"], series["solar_context"]
    assert len(rows) == 120
    assert [r["year"] for r in rows] == list(range(2200, 2320))
    assert context == timing["solar_year_context"]
    assert context["public_model_years_extended"] is False
    selected = timing["selected"]
    assert selected["year"] == 2319 and selected["ganzhi"] == rows[-1]["ganzhi"]
    assert selected["year_start_boundary"]["year"] == 2319
    assert selected["year_end_boundary"]["year"] == 2320
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
    assert len(series["rows"]) == 120


def test_future_lichun_uses_retained_point_and_outside_horizon_is_rejected(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    pivot = resolve_projection_boundary(
        2319, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    at = datetime.fromisoformat(pivot.term.calendar.utc.isoformat())
    for shift in (-1, 0, 1):
        query = at + timedelta(seconds=shift)
        selected = build_canping_result(**INPUT, analysis_datetime=query.isoformat())[
            "canping_timing"
        ]["selected"]
        assert selected["year"] == (
            2318
            if utc_calendar(query).julian_day_exact() < pivot.term.point.day
            else 2319
        )
    end_b = resolve_projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    with pytest.raises(ValueError, match="超出本次年序"):
        build_canping_result(
            **INPUT,
            analysis_datetime=(
                datetime.fromisoformat(end_b.term.calendar.utc.isoformat())
                + timedelta(seconds=1)
            ).isoformat(),
        )
    with pytest.raises(ValueError, match="早于出生"):
        build_canping_result(**INPUT, analysis_datetime="2200-01-01T00:00:00Z")


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


@pytest.mark.parametrize("year,horizon", [(2321, 120), (2320, 119), (2201, True)])
def test_derived_event_permission_remains_bounded(
    year: int, horizon: bool | int
) -> None:
    with pytest.raises(ValueError):
        projection_boundary(
            year, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=horizon
        )


def test_public_year_grid_is_not_extended(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    projection_boundary(
        2320, "UTC", origin_civil_year=2200, origin_bazi_year=2200, horizon=120
    )
    with pytest.raises(ValueError, match="1800..2200"):
        almanac.get_solar_terms_for_year(2320, "UTC")


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


def test_canping_latency_and_audit_payload_budget() -> None:
    build_canping_result(
        date="1990-06-15",
        time="09:33",
        timezone="+08:00",
        gender="男",
        method="ming",
        use_true_solar_time=False,
    )
    t0 = time.perf_counter()
    res = build_canping_result(
        date="1990-06-15",
        time="09:33",
        timezone="+08:00",
        gender="男",
        method="ming",
        use_true_solar_time=False,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    payload_bytes = len(json.dumps(res, ensure_ascii=False))
    assert elapsed_ms < 15.0, f"Canping took {elapsed_ms:.2f}ms >= 15ms"
    assert payload_bytes < 25 * 1024, f"Canping audit payload {payload_bytes}B >= 25KB"
