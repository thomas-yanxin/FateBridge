"""Source changes invalidate roots and pillars; synthetic kernels are not oracles."""

import asyncio
import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.astro import time_scales, utc_policy
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.solar_term_runtime import solar_term_cache_context
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, call_cli, native
from tests.test_liuyao_clash_transports import all_surfaces

pytest_plugins = ["tests.test_agentic_nested_outputs"]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clean_context(monkeypatch):
    # Original native/JPL selector and native solver-fault controls.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    previous = configured_ephemeris_path()
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    almanac.get_solar_terms_for_year.cache_clear()
    BaZiCalendar._get_four_pillars_cached.cache_clear()
    try:
        yield
    finally:
        monkeypatch.undo()
        configure_ephemeris_path(previous if previous is not None else "")
        almanac.get_solar_terms_for_year.cache_clear()
        BaZiCalendar._get_four_pillars_cached.cache_clear()


def symbolic(monkeypatch, observation):
    calls = []

    def solve(year, longitude, anchor, provenance=None):
        seconds = observation()
        calls.append(seconds)
        if provenance is not None:
            provenance.update(
                ephemeris_model="jpl" if os.getenv("FATEBRIDGE_JPL_FILE") else "swieph",
                ephemeris_retflags=(1,) if os.getenv("FATEBRIDGE_JPL_FILE") else (2,),
                ephemeris_library_version="synthetic-cache-test",
            )
        return anchor + timedelta(seconds=seconds)

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    return calls


def test_real_warm_cache_cannot_bypass_missing_strict_kernel(monkeypatch):
    moment = datetime(2026, 2, 4, 5)
    before = almanac.get_solar_terms_for_year(2026)
    assert all(t.resolution_provider == "swisseph" for t in before)
    BaZiCalendar.get_four_pillars(moment)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing-liuyao-v19.eph")
    with pytest.raises(EphemerisSourceError):
        almanac.get_solar_terms_for_year(2026)
    with pytest.raises(EphemerisSourceError):
        BaZiCalendar.get_four_pillars(moment)


def test_invalid_selector_is_checked_before_a_cache_hit(monkeypatch):
    symbolic(monkeypatch, lambda: 1)
    almanac.get_solar_terms_for_year(2026)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "../invalid.eph")
    with pytest.raises(EphemerisSourceError):
        almanac.get_solar_terms_for_year(2026)


def test_explicit_jpl_requires_native_library_even_for_cache_context(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "selected.eph")
    monkeypatch.setattr(almanac, "swe", None)
    with pytest.raises(ImportError, match="explicitly selected JPL"):
        almanac.get_solar_terms_for_year(2026)


def test_switching_selectors_recalculates_and_restoring_reuses_same_context(
    monkeypatch,
):
    calls = symbolic(
        monkeypatch,
        lambda: {None: 0, "synthetic-a.eph": 1, "synthetic-b.eph": 9}[
            os.getenv("FATEBRIDGE_JPL_FILE")
        ],
    )
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-a.eph")
    a = almanac.get_solar_terms_for_year(2026, "UTC")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-b.eph")
    b = almanac.get_solar_terms_for_year(2026, "UTC")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    assert almanac.get_solar_terms_for_year(2026, "UTC") is before
    assert len(calls) == 72
    assert (a[0].moment - before[0].moment).total_seconds() == 1
    assert (b[0].moment - a[0].moment).total_seconds() == 8
    assert a[0].ephemeris_model == b[0].ephemeris_model == "jpl"


def test_selected_kernel_install_replace_remove_invalidates_cache(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    configure_ephemeris_path(str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-marker.eph")
    marker = tmp_path / "synthetic-marker.eph"
    symbolic(monkeypatch, lambda: int(marker.read_text()) if marker.exists() else 1)
    before = almanac.get_solar_terms_for_year(2026, "UTC")
    marker.write_text("4")
    installed = almanac.get_solar_terms_for_year(2026, "UTC")
    replacement = tmp_path / "replacement"
    replacement.write_text("9")
    replacement.replace(marker)
    replaced = almanac.get_solar_terms_for_year(2026, "UTC")
    marker.unlink()
    removed = almanac.get_solar_terms_for_year(2026, "UTC")
    assert (installed[0].moment - before[0].moment).total_seconds() == 3
    assert (replaced[0].moment - installed[0].moment).total_seconds() == 5
    assert removed[0].moment == before[0].moment


def test_observed_selector_change_discards_partial_year(monkeypatch):
    first = True

    def observe():
        nonlocal first
        selected = os.getenv("FATEBRIDGE_JPL_FILE")
        if first:
            first = False
            monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-a.eph")
        return 1 if selected else 0

    calls = symbolic(monkeypatch, observe)
    terms = almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) > 24
    assert all(
        t.moment == almanac._solar_term_utc_via_linear(2026, i) + timedelta(seconds=1)
        for i, t in enumerate(terms)
    )


def test_selector_aba_between_terms_is_observed_and_bounded(monkeypatch):
    def observe():
        selected = os.getenv("FATEBRIDGE_JPL_FILE")
        if selected:
            monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
        else:
            monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-a.eph")
        return 1 if selected else 0

    calls = symbolic(monkeypatch, observe)
    with pytest.raises(RuntimeError, match="持续变化"):
        almanac.get_solar_terms_for_year(2026, "UTC")
    assert len(calls) <= 2


def hypothetical_table(monkeypatch):
    table = copy.deepcopy(utc_policy.leap_table())
    monkeypatch.setattr(utc_policy, "leap_table", lambda: table)
    return table


def add_fictional_future_leap(table):
    # Test-only counterfactual. This is not a future IERS announcement.
    table["entries"].append(
        {"effective_date": "2027-01-01", "tai_minus_utc_seconds": 38}
    )
    table["expires_at"] = "2030-01-01T00:00:00+00:00"
    table["bulletin"] = "FICTIONAL v19 cache regression profile"


def test_loaded_clock_profile_content_is_part_of_the_key(monkeypatch):
    table = hypothetical_table(monkeypatch)
    original = copy.deepcopy(table)
    before = solar_term_cache_context(almanac.swe)
    add_fictional_future_leap(table)
    assert solar_term_cache_context(almanac.swe) != before
    table.clear()
    table.update(original)
    assert solar_term_cache_context(almanac.swe) == before


def test_real_future_roots_keep_tt_and_relabel_utc_when_loaded_profile_changes(
    monkeypatch,
):
    table = hypothetical_table(monkeypatch)
    before = almanac.get_solar_terms_for_year(2028, "UTC")
    old_tt = [time_scales.ephemeris_time(t.moment).jd_tt for t in before]
    add_fictional_future_leap(table)
    after = almanac.get_solar_terms_for_year(2028, "UTC")
    assert after is not before
    for old, new, tt in zip(before, after, old_tt):
        assert abs((new.moment - old.moment).total_seconds() + 1) < 0.0002
        assert abs((time_scales.ephemeris_time(new.moment).jd_tt - tt) * 86400) < 0.0002


def test_derived_year_and_month_cache_follow_loaded_clock_profile(monkeypatch):
    table = hypothetical_table(monkeypatch)
    lichun = next(
        t for t in almanac.get_solar_terms_for_year(2028, "UTC") if t.name == "立春"
    )
    moment = lichun.moment - timedelta(seconds=0.5)
    before = BaZiCalendar.get_four_pillars(moment, "UTC")
    add_fictional_future_leap(table)
    after = BaZiCalendar.get_four_pillars(moment, "UTC")
    assert before["year"] == ("丁", "未") and before["month"][1] == "丑"
    assert after["year"] == ("戊", "申") and after["month"][1] == "寅"
    assert before["day"] == after["day"] and before["hour"] == after["hour"]


@pytest.mark.parametrize("name,target,anchor", [("小寒", 285, 6), ("大寒", 300, 20)])
def test_real_limited_de441_kernel_against_reused_de440_tt_reference(
    monkeypatch, name, target, anchor
):
    monkeypatch.setenv("SE_EPHE_PATH", str(FIXTURES))
    configure_ephemeris_path(str(FIXTURES))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "astrodice-de441-j2000.eph")
    provenance = {}
    root = almanac._solar_term_utc_via_swe(
        2000, target, datetime(2000, 1, anchor, tzinfo=timezone.utc), provenance
    )
    row = next(
        r
        for r in json.loads(
            (FIXTURES / "bazi_all_terms_v1/reference.json").read_text()
        )["rows"]
        if r["year"] == 2000 and r["name"] == name
    )
    assert root is not None and provenance["ephemeris_model"] == "jpl"
    assert abs((time_scales.ephemeris_time(root).jd_tt - row["jd_tt"]) * 86400) <= 1


def test_synthetic_source_switch_changes_public_year_month(
    rest, tmp_path, capsys, monkeypatch
):
    def solve(year, longitude, anchor, provenance=None):
        if provenance is not None:
            provenance.update(
                ephemeris_model="jpl" if os.getenv("FATEBRIDGE_JPL_FILE") else "swieph",
                ephemeris_retflags=(1,) if os.getenv("FATEBRIDGE_JPL_FILE") else (2,),
                ephemeris_library_version="synthetic-cache-test",
            )
        if longitude == 315:
            return datetime(
                year,
                2,
                5 if os.getenv("FATEBRIDGE_JPL_FILE") else 4,
                tzinfo=timezone.utc,
            )
        return anchor

    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", solve)
    payload = dict(date="2026-02-04", time="12:00:00", zone="UTC", gua_code="000000")
    fields = ["calendar_context", "nongli.yearGanZi", "nongli.monthGanZi"]
    before = all_surfaces(payload, fields, rest, tmp_path, capsys)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "synthetic-selected.eph")
    after = all_surfaces(payload, fields, rest, tmp_path, capsys)
    assert before[0]["calendar_context"] != after[0]["calendar_context"]
    assert before[0]["nongli"]["yearGanZi"] == "丙午"
    assert after[0]["nongli"]["yearGanZi"] == "乙巳"
    assert before[0]["nongli"]["monthGanZi"].endswith("寅")
    assert after[0]["nongli"]["monthGanZi"].endswith("丑")


@pytest.mark.parametrize("problem", ["missing", "invalid", "native_unavailable"])
def test_strict_source_failure_after_warm_year_survives_public_surfaces(
    problem, rest, tmp_path, capsys, monkeypatch
):
    almanac.get_solar_terms_for_year(2026)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing-liuyao-v19.eph")
    if problem == "invalid":
        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "../invalid.eph")
    elif problem == "native_unavailable":
        monkeypatch.setattr(almanac, "swe", None)
    spec = SPECS["sixyao"]
    payload = dict(date="2026-02-04", time="05:00:00", gua_code="000000")
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert response.status_code == 503 and code == 1 and protocol.is_error
    error = (
        "dependency_missing"
        if problem == "native_unavailable"
        else "ephemeris_source_inconsistent"
    )
    outputs = [response.json(), cli, json.loads(protocol.content[0].text)]
    for output in outputs:
        assert output["error_code"] == error and output["retryable"] is False
        assert "liuyao_evidence" not in output
        if problem != "native_unavailable":
            assert output["issues"][0]["path"] == "runtime.ephemeris_data"
