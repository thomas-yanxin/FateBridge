"""Source dependencies follow actual years; actual default labels stay faithful."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import almanac, calendar, de440_solar, timing
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import rest
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

MODEL = "fatebridge_de440_solar_v1"
PAYLOAD = dict(
    date="1972-12-07",
    time="00:18:43.043390",
    zone="UTC",
    gua_code="111111",
    changed_code="111111",
    focus_line=4,
    timing_days=0,
)


@pytest.fixture(autouse=True)
def auto_without_external_files(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    for key in [
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "FATEBRIDGE_JPL_FILE",
        "FATEBRIDGE_SOLAR_SPK_FILE",
    ]:
        monkeypatch.delenv(key, raising=False)


def unavailable(profile_id=None):
    raise EphemerisSourceError("solar_de440_invalid")


@pytest.mark.parametrize("year", [1700, 1799, 2201, 2300])
def test_whole_year_native_path_does_not_resolve_unused_de440(year, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    native = almanac.get_solar_terms_for_year(year, "UTC")
    # These four years now belong to the extended packaged DE440 range.
    # Explicit native selection must still avoid the unselected source.
    before = almanac.get_solar_terms_for_year(year, "UTC")
    assert [t.as_dict() for t in before] == [t.as_dict() for t in native]
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    assert almanac.get_solar_terms_for_year(year, "UTC") is before
    almanac.get_solar_terms_for_year.cache_clear()
    after = almanac.get_solar_terms_for_year(year, "UTC")
    assert [t.as_dict() for t in after] == [t.as_dict() for t in native]
    assert {t.ephemeris_model for t in after} == {"moshier"}


@pytest.mark.parametrize("year", [1799, 1800, 2200, 2201])
def test_derived_cache_still_requires_actual_adjacent_packaged_years(year, monkeypatch):
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    with pytest.raises(EphemerisSourceError) as caught:
        almanac.get_solar_term_environment_key(year=year)
    assert caught.value.reason == "solar_de440_invalid"


@pytest.mark.parametrize("consumer", ["four_pillars", "month", "day"])
def test_derived_cache_routes_the_actual_local_civil_year(consumer, monkeypatch):
    # Cache argument routing only; not a celestial comparison or new sample.
    instant = datetime.fromisoformat("1798-12-31T18:00:00+00:00")
    module = calendar if consumer == "four_pillars" else timing

    def observe(*, year):
        assert year == 1799
        raise RuntimeError("observed local civil year")

    monkeypatch.setattr(module, "get_solar_term_environment_key", observe)
    with pytest.raises(RuntimeError, match="observed local civil year"):
        if consumer == "four_pillars":
            calendar.BaZiCalendar.get_four_pillars(instant, "Asia/Shanghai")
        elif consumer == "month":
            timing.TimingAnalysis.calculate_liuyue(
                1798, 12, 31, "Asia/Shanghai", instant
            )
        else:
            timing.TimingAnalysis.calculate_liuri(instant, "Asia/Shanghai")


@pytest.mark.parametrize("project", [False, True])
def test_default_near_boundary_month_and_explanation_on_all_protocols(
    project, rest, tmp_path, capsys
):
    fields = ["liuyao_evidence.calendar_conventions.month_branch"] if project else None
    for output in all_surfaces(PAYLOAD, fields, rest, tmp_path, capsys):
        assert output["liuyao_evidence"]["calendar_conventions"]["month_branch"] == "亥"
        metadata = output["run_metadata"]
        assert MODEL in metadata["provenance"]["ephemeris_model"]
        assert metadata["runtime"]["solar_term_policy"]["model_id"] == MODEL
        assert metadata["runtime"]["solar_term_policy"]["accuracy_certified"] is False
        if not project:
            focus = output["liuyao_evidence"]["conditional_analysis"][
                "month_break_conditions"
            ]["focus"]
            assert focus["raw_month_break"] is False
            lines = [
                line
                for line in output["snapshot_text"].splitlines()
                if line.startswith("第4爻：月令层")
            ]
            assert len(lines) == 1 and "月破" not in lines[0]


def test_default_same_run_sha_restores_actual_source_and_month(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "default-de440-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(PAYLOAD, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        assert (
            original["liuyao_evidence"]["calendar_conventions"]["month_branch"] == "亥"
        )
        assert (
            original["run_metadata"]["runtime"]["solar_term_policy"]["model_id"]
            == MODEL
        )


def test_selected_source_corruption_still_fails_and_explicit_range_still_refuses(
    monkeypatch,
):
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    with pytest.raises(EphemerisSourceError) as caught:
        build_sixyao_result(**PAYLOAD)
    assert caught.value.reason == "solar_de440_invalid"
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(1699, "UTC")


def test_selected_default_fault_is_structured_on_three_protocols(
    monkeypatch, rest, tmp_path, capsys
):
    import asyncio

    from tests.test_agentic_nested_outputs import SPECS, call_cli, native

    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    spec = SPECS["sixyao"]
    http = rest.post(spec.rest_path, json=PAYLOAD)
    protocol = asyncio.run(native(spec, PAYLOAD))
    code, cli = call_cli(spec, PAYLOAD, tmp_path, capsys)
    assert http.status_code == 503 and protocol.is_error and code != 0
    for output in [http.json(), cli]:
        assert output["retryable"] is False
        assert "solar_de440_invalid" in str(output["issues"])
        assert "liuyao_evidence" not in output


def test_actual_default_warm_cache_cannot_bypass_missing_strict_jpl(monkeypatch):
    terms = almanac.get_solar_terms_for_year(2026, "UTC")
    assert {term.ephemeris_model for term in terms} == {MODEL}
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing-v29-strict.eph")
    with pytest.raises(EphemerisSourceError):
        almanac.get_solar_terms_for_year(2026, "UTC")


def test_strict_native_selection_does_not_load_unselected_packaged_source(monkeypatch):
    from fatebridge.core.solar_model_policy import solar_model_cache_key

    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing-v29-strict.eph")
    monkeypatch.setattr(de440_solar, "_profile", unavailable)
    assert solar_model_cache_key(year=1700) == ("auto", "native_strict_jpl")
    assert solar_model_cache_key(year=2026) == ("auto", "native_strict_jpl")
