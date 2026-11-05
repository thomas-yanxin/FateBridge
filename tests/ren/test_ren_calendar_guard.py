"""Endpoint-year support uses adjacent roots without expanding public years."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.de440_solar import MODEL_ID
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import AS_OF, SPECS, business, native, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/ren_calendar_guard_v1"
FREEZE_SHA = "7f93b89d2761b854672530e7d60bf99e201cfa962c80a63b3947d776c48f47d9"
CASES = [
    (1800, 1, 1),
    (1800, 7, 1),
    (1800, 12, 31),
    (2200, 1, 1),
    (2200, 7, 1),
    (2200, 12, 31),
]


def references():
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(CORPUS / "freeze.json") == FREEZE_SHA
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    assert all(
        digest(CORPUS / name) == checksum for name, checksum in frozen["files"].items()
    )
    return json.loads((CORPUS / "reference.json").read_text())["rows"]


@pytest.fixture
def empty_ephemeris(monkeypatch, tmp_path):
    original = configured_ephemeris_path()
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        with monkeypatch.context() as environment:
            environment.setenv("SE_EPHE_PATH", str(tmp_path))
            environment.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            environment.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
            yield
    finally:
        # Restore the environment before calling a function that honors it.
        configure_ephemeris_path(original)
        almanac.get_solar_terms_for_year.cache_clear()


@pytest.mark.parametrize("mode", ["auto", "de440"])
@pytest.mark.parametrize("date_parts", CASES)
@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_endpoint_years_on_three_transports(
    mode, date_parts, key, empty_ephemeris, monkeypatch, surface_calls
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    year, month, day = date_parts
    payload = dict(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_minute=0,
        analysis_second=0,
        analysis_timezone="UTC",
        use_true_solar_time=False,
    )
    if key == "jinkou":
        payload["di_fen"] = "酉"
    spec = SPECS[key]
    section = "jinkou" if key == "jinkou" else "liureng"
    fields = ["four_pillars", section + ".calendar_policy", section + ".ruleset"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http, mcp, code, cli = surface_calls(
        spec, payload, projection=opts, cli_first=False, rest_as_of=AS_OF
    )
    assert http.status_code == 200, http.text
    assert not mcp.is_error, mcp.structured_content
    assert code == 0, cli
    values = [http.json(), mcp.structured_content, cli]
    assert business(values[0]) == business(values[1]) == business(values[2])
    expected_names = {
        1: ["冬至", "小寒", "大雪", "小寒", "立春"],
        7: ["夏至", "小暑", "芒种", "小暑", "立春"],
        12: ["冬至", "小寒", "大雪", "小寒", "立春"],
    }[month]
    for value in values:
        deps = value[section]["calendar_policy"]["solar_term_dependencies"]
        assert [x["name"] for x in deps] == expected_names
        assert {x["ephemeris_model"] for x in deps} == {MODEL_ID}
        assert {x["provider"] for x in deps} == {"jpl_de440"}
        assert all(x["ephemeris_retflags"] == [] for x in deps)
        assert value["four_pillars"]["month"]["branch"] == (
            "午" if month == 7 else "子"
        )
        assert value[section]["ruleset"]["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize("mode", ["auto", "de440", "analytic"])
@pytest.mark.parametrize("origin", [1800, 2200])
def test_all_adjacent_year_roots_use_the_selected_source_and_independent_reference(
    mode, origin, empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    moment = datetime(origin, 1 if origin == 1800 else 12, 1, tzinfo=timezone.utc)
    window = almanac._term_window(moment, "UTC")
    reference = {(r["year"], r["index"]): r for r in references()}
    checked = 0
    for term in window:
        key = (term.moment.year, almanac.SOLAR_TERM_NAMES.index(term.name))
        if key not in reference:
            continue
        assert term.resolution_provider == (
            "fatebridge_analytic" if mode == "analytic" else "jpl_de440"
        )
        details = term.solar_model_details
        assert (
            abs(details["selected_crossing_jd_tt"] - reference[key]["jd_tt"]) * 86400
            <= 1.0
        )
        if key[0] in {1799, 2201}:
            assert details["adjacent_boundary_context_year"] == origin
            assert details["solar_model_input_years"] == [1800, 2200]
        checked += 1
    assert checked == 48


@pytest.mark.parametrize("outside,origin", [(1699, 1700), (2301, 2300)])
def test_guard_cache_never_authorizes_a_public_outside_year(
    outside, origin, empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    almanac._term_window(datetime(origin, 7, 1, tzinfo=timezone.utc), "UTC")
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(outside, "UTC")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    standalone = almanac.get_solar_terms_for_year(outside, "UTC")
    assert all(x.resolution_provider == "swisseph" for x in standalone)
    guarded = almanac._term_window(datetime(origin, 7, 1, tzinfo=timezone.utc), "UTC")
    guard = [x for x in guarded if x.moment.year == outside]
    assert len(guard) == 24 and all(x.resolution_provider == "jpl_de440" for x in guard)
    assert almanac.get_solar_terms_for_year(outside, "UTC") is standalone


def test_guard_source_failure_does_not_fall_back_to_native(
    empty_ephemeris, monkeypatch
):
    import fatebridge.core.de440_solar as source

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    original = source.longitude_crossing_tt_parts

    def fail_guard(longitude, low, high):
        if low < 2378496.5:  # Jan1,1800; a guard-year root only.
            raise EphemerisSourceError("solar_de440_invalid")
        return original(longitude, low, high)

    monkeypatch.setattr(source, "longitude_crossing_tt_parts", fail_guard)
    with pytest.raises(EphemerisSourceError, match="coefficients"):
        almanac.get_adjacent_solar_terms(
            datetime(1800, 1, 1, tzinfo=timezone.utc), "UTC"
        )
    monkeypatch.setattr(source, "longitude_crossing_tt_parts", original)
    previous, _ = almanac.get_adjacent_solar_terms(
        datetime(1800, 1, 1, tzinfo=timezone.utc), "UTC"
    )
    assert previous.resolution_provider == "jpl_de440"


@pytest.mark.parametrize("origin", [1800, 2200])
def test_bazi_year_month_and_native_control_remain_explicit(
    origin, empty_ephemeris, monkeypatch
):
    moment = datetime(origin, 1, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    assert almanac.get_bazi_year(moment, "UTC") == origin - 1
    assert almanac.get_bazi_month_context(moment, "UTC")["branch"] == "子"
    assert BaZiCalendar.get_four_pillars(moment, "UTC")["month"][1] == "子"
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    current, following = almanac.get_adjacent_solar_terms(moment, "UTC")
    assert all(
        t.resolution_provider == "swisseph" and t.ephemeris_model == "moshier"
        for t in [current, following]
    )


@pytest.mark.parametrize("key", ["liureng_gods", "jinkou"])
def test_guard_corruption_is_a_failure_on_every_transport_before_projection(
    key, empty_ephemeris, monkeypatch, surface_calls
):
    import fatebridge.core.de440_solar as source

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    original = source.longitude_crossing_tt_parts

    def fail_guard(longitude, low, high):
        if low < 2378496.5:
            raise EphemerisSourceError("solar_de440_invalid")
        return original(longitude, low, high)

    monkeypatch.setattr(source, "longitude_crossing_tt_parts", fail_guard)
    payload = dict(
        analysis_year=1800,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=12,
        analysis_timezone="UTC",
        use_true_solar_time=False,
    )
    if key == "jinkou":
        payload["di_fen"] = "酉"
    spec = SPECS[key]
    http, mcp, code, cli = surface_calls(
        spec,
        payload,
        params={"fields": "analysis_type", "strict_fields": "true", "as_of": AS_OF},
        options={"fields": ["analysis_type"], "strict_fields": True},
        flags=["--fields", "analysis_type", "--strict-fields", "true"],
        cli_first=False,
    )
    assert http.status_code == 503 and mcp.is_error and code == 1
    for got in [http.json(), mcp.structured_content, cli]:
        assert got["error_code"] == "ephemeris_source_inconsistent"
        assert got["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "solar_de440_invalid"}
        ]


@pytest.mark.parametrize(
    "year,context,message",
    [
        (1798, 1800, "Adjacent solar boundaries require an in-range context"),
        (2202, 2200, "Adjacent solar boundaries require an in-range context"),
        (1698, 1699, "Explicit packaged DE440 solar mode currently covers1700..2300"),
        (2302, 2301, "Explicit packaged DE440 solar mode currently covers1700..2300"),
    ],
)
def test_private_guard_requires_one_adjacent_year_of_a_supported_context(
    year, context, message, empty_ephemeris, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    with pytest.raises(ValueError) as error:
        almanac._solar_terms_for_context_year(year, "UTC", context)
    assert str(error.value) == message


def test_unused_scalar_solver_failure_does_not_impersonate_an_active_parts_failure(
    empty_ephemeris, monkeypatch
):
    import fatebridge.core.de440_solar as source

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")

    def scalar_failure(*args, **kwargs):
        raise EphemerisSourceError("solar_de440_invalid")

    monkeypatch.setattr(source, "longitude_crossing_tt", scalar_failure)
    previous, _ = almanac.get_adjacent_solar_terms(
        datetime(1800, 1, 1, tzinfo=timezone.utc), "UTC"
    )
    assert previous.resolution_provider == "jpl_de440"
    assert previous.solar_model_details["selected_crossing_tt_parts"]
    with pytest.raises(EphemerisSourceError):
        source.longitude_crossing_tt(270.0, 2378450.5, 2378480.5)
