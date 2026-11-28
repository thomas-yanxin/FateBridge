"""Tests for western_timing deduplication, selective execution, bounded windows, and transit scanning."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.requests.western_timing import (
    WesternTimingRequest,
    WesternTransitRequest,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.services.western_lifespan import calculate_jaynesprog
from fatebridge.services.western_timing import calculate_western_timing_analysis
from fatebridge.services.western_timing_tools import calculate_timing_tool
from tests.support.transports import business

DEMO = dict(
    name="演示甲",
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    birth_longitude=116.4074,
    birth_latitude=39.9042,
    analysis_year=2026,
    analysis_month=10,
    analysis_day=14,
    analysis_hour=12,
    analysis_minute=0,
)


def test_western_timing_default_bounds_timelines_and_deduplicates_blocks() -> None:
    default_res = calculate_western_timing_analysis(**DEMO)
    assert "error" not in default_res, default_res

    # Transits omit duplicate embedded natal_reference inside western_timing.
    assert "natal_reference" not in default_res["transits"]["current_transit"]
    assert default_res["natal_reference"]["lots"]

    # Primary directions keep windows + bounded nearby timeline (<= 25 entries within ±5y).
    pd = default_res["directions"]["primary_directions"]
    assert pd["current_window"]
    assert pd["past_window"]
    assert pd["future_window"]
    assert "exact_window" in pd
    assert pd["timeline_truncated"] is True
    assert pd["total_timeline_count"] > len(pd["timeline"])
    assert len(pd["timeline"]) <= 25
    assert all(
        abs(item["relative_years_from_current"]) <= 5.0 for item in pd["timeline"]
    )

    # Primary direction chart omits verbatim duplicated coordinate blocks when embedded.
    pdc = default_res["directions"]["primary_direction_chart"]
    assert pdc["hits"]
    for dup_key in (
        "coordinate_hits",
        "natal_coordinate_points",
        "natal_coordinate_lots",
        "directed_coordinate_points",
        "directed_coordinate_lots",
        "coordinate_diagnostics",
    ):
        assert dup_key not in pdc

    # Zodiacal releasing omits level_1..4 timelines by default.
    zr = default_res["time_lords"]["zodiacal_releasing"]
    for track_name in ("spirit", "fortune", "eros"):
        track = zr[track_name]
        assert track["lot"]
        assert track["current_level_1"] is not None
        for tl_key in (
            "level_1_timeline",
            "level_2_timeline",
            "level_3_timeline",
            "level_4_timeline",
        ):
            assert tl_key not in track

    # Firdaria omits full timeline by default while keeping current major/sub + subperiods.
    fird = default_res["time_lords"]["firdaria"]
    assert "timeline" not in fird
    assert fird["current_major"]["subperiods"]
    assert fird["current_sub"] is not None

    # Decennials omit full sublevel trees and timeline by default.
    dec = default_res["time_lords"]["decennials"]
    assert "timeline" not in dec
    for lvl in ("current_level_1", "current_level_2", "current_level_3"):
        assert dec[lvl] is not None
        assert "sublevel" not in dec[lvl]


def test_western_timing_include_full_timelines_restores_full_output() -> None:
    full_res = calculate_western_timing_analysis(**DEMO, include_full_timelines=True)
    assert "error" not in full_res, full_res

    pd = full_res["directions"]["primary_directions"]
    assert "timeline_truncated" not in pd
    assert len(pd["timeline"]) > 50

    zr = full_res["time_lords"]["zodiacal_releasing"]
    for track_name in ("spirit", "fortune", "eros"):
        assert len(zr[track_name]["level_1_timeline"]) > 0
        assert len(zr[track_name]["level_4_timeline"]) > 0

    fird = full_res["time_lords"]["firdaria"]
    assert len(fird["timeline"]) == 12

    dec = full_res["time_lords"]["decennials"]
    assert len(dec["timeline"]) == 7
    assert len(dec["current_level_1"]["sublevel"]) == 7


def test_western_timing_selective_techniques_and_validate_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.core.predictive.western_timing as wt

    def fail_called(*_args, **_kwargs):
        raise AssertionError("Unrequested technique engine should not be invoked")

    monkeypatch.setattr(wt, "build_return_payload", fail_called)
    monkeypatch.setattr(wt, "build_primary_direction_analysis", fail_called)
    monkeypatch.setattr(wt, "build_zodiacal_releasing_payload", fail_called)
    monkeypatch.setattr(wt, "build_decennials_payload", fail_called)

    spec = next(s for s in CATALOG if s.name == "western_timing")
    req = WesternTimingRequest(**DEMO, techniques=["firdaria", "transit"])
    raw = execute_with_receipt(
        spec,
        req,
        options=ExecutionOptions(as_of="2026-10-14T12:00:00+08:00"),
    )
    assert "error" not in raw, raw
    assert set(raw.keys()) == {
        "analysis_type",
        "analysis_context",
        "natal_reference",
        "transits",
        "time_lords",
        "summary",
        "run_metadata",
    }
    assert list(raw["time_lords"].keys()) == ["firdaria"]
    assert list(raw["transits"].keys()) == ["current_transit"]


def test_western_timing_default_delivery_budget_and_isomorphism() -> None:
    spec = next(s for s in CATALOG if s.name == "western_timing")
    req = spec.request_model.model_validate(DEMO)
    raw = execute_with_receipt(
        spec,
        req,
        options=ExecutionOptions(as_of="2026-10-14T12:00:00+08:00"),
    )
    delivered = deliver_response(raw, spec=spec)
    full = deliver_response(raw, spec=spec, include=["*"])
    size = len(json.dumps(delivered, ensure_ascii=False).encode("utf-8"))
    assert size <= 10240
    assert delivered["run_metadata"]["omitted_fields"] == list(spec.default_omit)
    assert "omitted_fields" not in full["run_metadata"]
    assert delivered["analysis_context"] == full["analysis_context"]
    assert delivered["time_lords"]["firdaria"] == full["time_lords"]["firdaria"]
    for view_name in ("stage", "annual", "short_term", "career"):
        view_out = deliver_response(raw, spec=spec, include=[view_name])
        assert view_out["summary"] == full["summary"]


def test_western_timing_rejects_empty_or_invalid_techniques() -> None:
    with pytest.raises(ValidationError):
        WesternTimingRequest(**DEMO, techniques=[])
    with pytest.raises(ValidationError):
        WesternTimingRequest(**DEMO, techniques=["nonexistent_technique"])


def test_transit_chart_scan_days_builds_timeline_and_validates_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.core.predictive.western_timing as wt

    natal_calls = 0
    orig_build_natal = wt.build_natal_subject

    def counted_natal(*args, **kwargs):
        nonlocal natal_calls
        natal_calls += 1
        return orig_build_natal(*args, **kwargs)

    monkeypatch.setattr(wt, "build_natal_subject", counted_natal)
    res = calculate_timing_tool("transit_chart", **DEMO, scan_days=14)
    assert "error" not in res, res
    assert natal_calls == 1
    tc = res["transit_chart"]
    assert tc["scan_days"] == 14
    timeline = tc["transit_timeline"]
    assert len(timeline) == 14
    assert timeline[0]["date"] == "2026-10-14"
    assert timeline[13]["date"] == "2026-10-27"
    assert timeline[0]["exact_hits"] == tc["exact_hits"]
    for step in timeline:
        assert "exact_hits" in step and "tight_hits" in step

    with pytest.raises(ValidationError):
        WesternTransitRequest(**DEMO, scan_days=0)
    with pytest.raises(ValidationError):
        WesternTransitRequest(**DEMO, scan_days=91)


def test_jaynesprog_reuses_natal_declinations_and_deduplicates_ephemeris(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.services.western_lifespan as wl

    decl_calls = 0
    orig_body_decls = wl._body_declinations

    def counted_body_decls(utc):
        nonlocal decl_calls
        decl_calls += 1
        return orig_body_decls(utc)

    monkeypatch.setattr(wl, "_body_declinations", counted_body_decls)
    res = calculate_jaynesprog(**DEMO)
    assert "error" not in res, res
    assert decl_calls == 1
    assert res["declination_progressions"]["parallels"]


def test_shared_analysis_subject_and_earth_attitude_and_firdaria_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.core.predictive.firdaria as fird
    import fatebridge.core.predictive.primary_directions as pd
    import fatebridge.core.predictive.profections as prof
    import fatebridge.core.predictive.transit as tr
    import fatebridge.core.predictive.western_timing as wt

    # 1. earth_attitude called once per PrimaryDirectionEquatorialContext (and pair).
    ea_calls = 0
    orig_ea = pd.earth_attitude

    def counted_ea(*args, **kwargs):
        nonlocal ea_calls
        ea_calls += 1
        return orig_ea(*args, **kwargs)

    monkeypatch.setattr(pd, "earth_attitude", counted_ea)
    from datetime import datetime

    from fatebridge.core.predictive._common import build_predictive_birth_info
    from fatebridge.utils.timezones import parse_timezone_name

    birth_info = build_predictive_birth_info(
        birth_year=DEMO["birth_year"],
        birth_month=DEMO["birth_month"],
        birth_day=DEMO["birth_day"],
        birth_hour=DEMO["birth_hour"],
        birth_minute=DEMO["birth_minute"],
        birth_timezone=DEMO["birth_timezone"],
        birth_longitude=DEMO["birth_longitude"],
        birth_latitude=DEMO["birth_latitude"],
        name=DEMO["name"],
    )
    natal_subject = wt.build_natal_subject(birth_info)
    dt = datetime(2026, 10, 14, 12, 0, tzinfo=parse_timezone_name("Asia/Shanghai"))
    wt._build_primary_direction_pair(
        birth_info,
        natal_subject,
        analysis_datetime=dt,
        pd_method="placidus",
        pd_time_key="Ptolemy",
        pd_type=0,
        pd_aspects=None,
        show_pd_bounds=True,
    )
    assert ea_calls == 1

    # 2. firdaria calendar_anniversary stops once 12 major periods are built.
    anniv_calls = 0
    orig_anniv = fird._calendar_anniversary

    def counted_anniv(birth, nominal_age):
        nonlocal anniv_calls
        anniv_calls += 1
        return orig_anniv(birth, nominal_age)

    monkeypatch.setattr(fird, "_calendar_anniversary", counted_anniv)
    fird_res = fird.build_firdaria_payload(
        birth_info,
        natal_subject,
        analysis_datetime=dt,
        firdaria_year_basis="calendar_anniversary",
        include_full_timelines=True,
    )
    assert len(fird_res["timeline"]) == 12
    assert anniv_calls == 12

    # 3. transit collect_aspect_hits called once (exact_hits filtered from hits),
    # and given_year reuses analysis_subject + transit_hits + profection dates.
    transit_aspect_calls = 0
    orig_collect_tr = tr.collect_aspect_hits

    def counted_collect_tr(**kwargs):
        nonlocal transit_aspect_calls
        transit_aspect_calls += 1
        return orig_collect_tr(**kwargs)

    birthday_calls = 0
    orig_resolve_bday = prof.resolve_last_birthday

    def counted_resolve_bday(*args, **kwargs):
        nonlocal birthday_calls
        birthday_calls += 1
        return orig_resolve_bday(*args, **kwargs)

    monkeypatch.setattr(tr, "collect_aspect_hits", counted_collect_tr)
    monkeypatch.setattr(prof, "resolve_last_birthday", counted_resolve_bday)
    monkeypatch.setattr(
        prof,
        "build_subject",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("should reuse analysis_subject")
        ),
    )
    monkeypatch.setattr(
        prof,
        "collect_aspect_hits",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("should reuse transit_hits")
        ),
    )
    pair_res = wt.build_western_timing_payload(
        birth_info,
        analysis_datetime=dt,
        techniques=["profection", "transit", "given_year"],
    )
    assert birthday_calls == 1
    assert transit_aspect_calls == 1
    assert pair_res["directions"]["given_year"]["hits"]


def test_transit_scan_rest_mcp_cli_parity(surface_calls) -> None:
    spec = next(s for s in CATALOG if s.name == "transit_chart")
    payload = {**DEMO, "scan_days": 5}
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert len(http.json()["transit_chart"]["transit_timeline"]) == 5
