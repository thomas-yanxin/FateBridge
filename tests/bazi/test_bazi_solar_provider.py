"""Availability guards are regressions, not independent celestial accuracy data."""

import asyncio
from dataclasses import replace
from datetime import datetime

import pytest

from fatebridge.core import almanac, timing
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.errors import EphemerisSourceError
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.evaluation.test_agentic_nested_outputs import SPECS, call_cli, inputs, native
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest


def clear_solar_caches():
    for function in (
        almanac.get_solar_terms_for_year,
        BaZiCalendar._get_four_pillars_cached,
        timing._calculate_liuyue_cached,
        timing._calculate_liuri_cached,
    ):
        function.cache_clear()


@pytest.fixture
def failed_solver(monkeypatch):
    # This original fault injects only the native solver. Its entire cohort
    # remains a native-control regression; default-source faults are separate.
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    clear_solar_caches()
    monkeypatch.setattr(almanac, "_solar_term_utc_via_swe", lambda *a, **kw: None)
    try:
        yield
    finally:
        # A negative-path test must not leave successful coarse values in the
        # shared year or derived caches for the next test/provider.
        clear_solar_caches()


rest = _shared_rest


@pytest.mark.parametrize(
    "key",
    ["bazi_" + topic for topic in TOPICS]
    + [
        "timing_analysis",
        "dayun_analysis",
        "liunian_analysis",
        "liuyue_analysis",
        "liuri_analysis",
        "liushi_analysis",
        "jieqi_timeline_analysis",
    ],
)
def test_missing_native_crossings_are_rejected_on_all_three_surfaces(
    key, rest, tmp_path, capsys, failed_solver
):
    spec = SPECS[key]
    payload = {**inputs(spec), "use_true_solar_time": False}
    http = rest.post(spec.rest_path, json=payload)
    code, local = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 503 and code != 0 and protocol.is_error
    for envelope in (http.json(), local, protocol.structured_content):
        assert envelope["error_code"] == "ephemeris_source_inconsistent"
        assert envelope["issues"][0]["code"] == "solar_native_unavailable"
        assert envelope["retryable"] is False
        assert not any(k in envelope for k in ("bazi_birth", "four_pillars", "liuyue"))
    assert "solar_native_unavailable" in str(protocol.content)


@pytest.mark.parametrize("provider", ["linear_1900_fallback", "unknown", ""])
def test_unknown_provenance_is_not_promoted_to_a_calculated_term(provider):
    term = almanac.SolarTerm("立春", datetime(2026, 2, 4), "20260204", "", provider)
    with pytest.raises(RuntimeError, match="swisseph"):
        almanac.require_calculated_solar_term(term)


@pytest.mark.parametrize(
    "operation",
    [
        lambda: almanac.get_bazi_year(datetime(2026, 2, 4, 7, 9)),
        lambda: almanac.get_bazi_month_context(datetime(2026, 2, 4, 7, 9)),
        lambda: TimingAnalysis.calculate_liunian(
            2026, moment=datetime(2026, 2, 4, 7, 9)
        ),
        lambda: TimingAnalysis.calculate_liuyue(2026, 2, 4),
        lambda: TimingAnalysis.calculate_liuri(datetime(2026, 2, 4)),
        lambda: TimingAnalysis.calculate_dayun_start_details(
            datetime(2026, 2, 4), "男"
        ),
        lambda: TimingAnalysis.calculate_liuyue_timeline(2026),
        lambda: TimingAnalysis.calculate_jieqi_transition_timeline(2026),
    ],
)
def test_direct_domain_operations_reject_missing_native_roots(operation, failed_solver):
    with pytest.raises(EphemerisSourceError, match="no linear approximation"):
        operation()


def test_pure_sexagenary_arithmetic_does_not_require_astronomy(failed_solver):
    assert TimingAnalysis.calculate_liunian(2026)["pillar"] == "丙午"
    assert BaZiCalendar.calculate_day_pillar(2026, 2, 4) == ("己", "酉")


@pytest.mark.parametrize("name", ["立春", "惊蛰", "春分"])
def test_actual_consumed_boundary_is_checked_even_when_other_terms_are_available(
    name, monkeypatch
):
    # Keep all calculated values, alter ONLY one term's provenance. The
    # guard must inspect the consumed object, not another year/provider probe.
    terms = almanac.get_solar_terms_for_year(2026)
    tainted = tuple(
        replace(t, resolution_provider="linear_1900_fallback") if t.name == name else t
        for t in terms
    )
    original = almanac.get_solar_terms_for_year
    monkeypatch.setattr(
        almanac,
        "get_solar_terms_for_year",
        lambda year, zone: tainted if year == 2026 else original(year, zone),
    )
    probe = next(t for t in terms if t.name == name).moment
    with pytest.raises(RuntimeError, match="swisseph"):
        if name == "立春":
            almanac.get_bazi_year(probe)
        elif name == "惊蛰":
            almanac.get_bazi_month_boundaries(probe)
        else:
            almanac.build_calendar_context(probe)
