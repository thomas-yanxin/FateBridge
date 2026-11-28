"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import math
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.core import almanac, de441_solar, solar_term_clock
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.meihua.tongshefa import build_tongshefa_result
from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
from fatebridge.services import run_metadata
from fatebridge.services.run_metadata import (
    attach_run_metadata,
    engine_is_approximate,
    resolve_runtime_engine,
)
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.places import resolve_coordinates as _resolve_coordinates
from tests.support.output_facts import canonical_json
from tests.support.transports import (
    SPECS,
    cached_mcp_app,
    call_calculation,
    native,
    rest,
    surface_calls,
)


def test_decimal_and_direction_coordinates() -> None:
    cases = [
        (0, "longitude", 0),
        (0, "latitude", 0),
        ("121e30", "longitude", 121.5),
        ("31s15", "latitude", -31.25),
        ("-180", "longitude", -180),
        ("90N0", "latitude", 90),
        ("31n59.999999999999999", "latitude", 32),
        ("1.0000000000000001n0.000000000000006", "latitude", 1.0000000000000002),
        (None, "latitude", None),
        ("", "longitude", None),
    ]
    for value, axis, expected in cases:
        assert parse_geo_coordinate(value, axis=axis) == expected


def test_invalid_coordinates_never_fall_back_to_a_default() -> None:
    cases = [
        ("31N90", "latitude"),
        ("190", "longitude"),
        ("90.000000000000001", "latitude"),
        ("180E0.000000000000001", "longitude"),
        (-91, "latitude"),
        (float("nan"), "longitude"),
        (float("inf"), "latitude"),
        ("31E13", "latitude"),
        ("121N28", "longitude"),
        ("bad", "longitude"),
        ("-31N0", "latitude"),
        (True, "latitude"),
    ]
    for value, axis in cases:
        with pytest.raises(ValueError):
            parse_geo_coordinate(value, axis=axis)


@pytest.mark.parametrize("latitude,longitude", [(0, 0), (0, 32.5), (51.5, 0)])
def test_zero_coordinates_are_preserved(
    latitude: float | int, longitude: float | int
) -> None:
    assert _resolve_coordinates(gps_lat=latitude, gps_lon=longitude) == (
        latitude,
        longitude,
    )


def test_gps_coordinates_take_precedence_over_text_hints() -> None:
    assert _resolve_coordinates(lat="bad", lon="bad", gps_lat=0, gps_lon=0) == (0, 0)


def test_empty_required_clock_fails_on_every_transport(rest, surface_calls) -> None:
    cases = [
        ("liuyao", {"method": "time"}),
        ("liuyao", {"method": "coin", "seed": 42}),
        ("liuyao", {"coins": [6, 7, 8, 9, 7, 8]}),
        ("liuyao", {"gua_code": "111111"}),
        ("sanshi_combined_chart", {}),
    ]
    surface_targets = {("liuyao", "   "), ("sanshi_combined_chart", "   ")}
    for key, options in cases:
        spec = SPECS[key]
        for clock in ("", "   "):
            payload = {"date": "2026-02-10", "time": clock, **options}
            if (key, clock) in surface_targets:
                surface_targets.remove((key, clock))
                response, protocol, code, local = surface_calls(spec, payload)
                assert response.status_code == 400 and code == 1 and protocol.is_error
                outputs = (response.json(), local, protocol.structured_content)
            else:
                response = rest.post(spec.rest_path, json=payload)
                assert response.status_code == 400
                outputs = (response.json(),)
            for output in outputs:
                assert output["error_code"] == "validation_error"
                assert "time" in output["error"]
                assert "run_metadata" not in output


@pytest.mark.parametrize("year", [1799, 1800, 2200, 2201])
def test_all_original_native_events_select_the_first_post_crossing_point(
    year: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_DE441_DIR", raising=False)
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term, target in zip(terms, almanac.SOLAR_TERM_LONGITUDES, strict=True):
        point = ephemeris_time(term.moment).jd_tt
        before = math.nextafter(point, -math.inf)
        assert term.resolution_provider == "swisseph"
        assert term.ephemeris_model == "moshier"
        left = (
            almanac.ephemeris_call("calc", before, swe.SUN, swe.FLG_SWIEPH)[0][0] % 360
        )
        right = (
            almanac.ephemeris_call("calc", point, swe.SUN, swe.FLG_SWIEPH)[0][0] % 360
        )
        assert math.remainder(left - target, 360) < 0, term.name
        assert math.remainder(right - target, 360) >= 0, term.name
        assert term.tt_instant is not None and term.tt_instant.days == point
        require_ren_solar_term(term)


def test_exact_crossing_at_the_first_scan_sample_is_not_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor = datetime(2000, 6, 1, tzinfo=timezone.utc)
    root = ephemeris_time(anchor).jd_tt - 30.0

    def linear_sun(operation, point, body, flags):
        assert operation == "calc" and body == swe.SUN
        return ((point - root) % 360, 0, 1, 1, 0, 0), swe.FLG_MOSEPH

    monkeypatch.setattr(almanac, "ephemeris_call", linear_sun)
    monkeypatch.setattr(
        de441_solar, "solar_longitude", lambda point: (point - root) % 360
    )
    provenance = {}
    moment = almanac._solar_term_utc_via_swe(2000, 0, anchor, provenance)
    assert moment is not None
    assert provenance["resolved_jd_tt"] == root
    assert ephemeris_time(moment).jd_tt == root


def test_new_post_crossing_contract_rejects_a_coherent_pre_crossing_point(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    term = almanac.get_solar_terms_for_year(2026, "UTC")[0]
    low = math.nextafter(ephemeris_time(term.moment).jd_tt, -math.inf)
    bad = replace(
        term,
        calendar=ZonedCalendar(
            solar_term_clock.native_solar_root_calendar(low), timezone.utc
        ),
    )
    with pytest.raises(EphemerisSourceError) as caught:
        require_ren_solar_term(bad)
    assert caught.value.reason == "ren_solar_term_point_inconsistent"


def test_current_facts_ignore_only_execution_receipts() -> None:
    payload = {
        "value": 1.0,
        "provenance": {"source": "primary"},
        "generated_at": "source-edition-date",
        "run_metadata": {"run_id": "first", "duration_ms": 1},
    }
    other = {**payload, "run_metadata": {"run_id": "second", "duration_ms": 2}}
    assert canonical_json(payload) == canonical_json(other)
    for field, replacement in (
        ("value", math.nextafter(1.0, math.inf)),
        ("provenance", {"source": "different"}),
        ("generated_at", "different-edition"),
    ):
        assert canonical_json(payload) != canonical_json(
            {**payload, field: replacement}
        )


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_current_facts_are_rejected(value) -> None:
    with pytest.raises(ValueError):
        canonical_json({"coordinate": value})


def test_domain_requests_build_nested_schemas() -> None:
    code = """
from fatebridge.core.requests.divination import SixYaoRequest
sixyao = SixYaoRequest.model_validate({'date': '2028-01-01', 'time': '00:00:00',
    'lines': [{'value': 1, 'change': True}] + [{'value': 0, 'change': False}] * 5})
assert len(sixyao.lines) == 6
assert sixyao.lines[0].value == 1 and sixyao.lines[0].change
assert 'SixYaoLineRequest' in SixYaoRequest.model_json_schema()['$defs']
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_catalog_cold_import_does_not_load_domain_engines() -> None:
    code = """
import sys
from fatebridge.services.tool_catalog import CATALOG
assert len({spec.name for spec in CATALOG}) == len(CATALOG)
for module in ('fatebridge.services.bazi',
               'fatebridge.services.astrology', 'fatebridge.services.western_timing'):
    assert module not in sys.modules, module
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_attach_run_metadata_uses_explicit_name() -> None:
    out = attach_run_metadata({"x": 1}, tool_name="bazi_wealth")
    assert out["run_metadata"]["tool_name"] == "bazi_wealth"


def test_run_metadata_flags_approximate_astro_engine() -> None:
    # Approximate / mixed astro backends -> degraded precision flag is True.
    approx = attach_run_metadata(
        {"chart_profile": {"engine_backend": "fatebridge_approximate_orbital_model"}},
        tool_name="astro_chart",
    )
    assert approx["run_metadata"]["engine_is_approximate"] is True
    mixed = attach_run_metadata(
        {"chart_profile": {"engine_precision": "mixed_precision_runtime_model"}},
        tool_name="astro_chart",
    )
    assert mixed["run_metadata"]["engine_is_approximate"] is True

    # Swiss-ephemeris precision and non-astro deterministic tools -> False.
    precise = attach_run_metadata(
        {"chart_profile": {"engine_backend": "swisseph_api"}}, tool_name="astro_chart"
    )
    assert precise["run_metadata"]["engine_is_approximate"] is False
    bazi = attach_run_metadata({"x": 1}, tool_name="bazi_wealth")
    assert bazi["run_metadata"]["engine_is_approximate"] is False


def test_run_metadata_flags_silent_moshier_downgrade() -> None:
    # swisseph backend reports a constant engine_precision/backend regardless of
    # whether .se1 data files exist; the real model is in ephemeris_model. A
    # silent downgrade to Moshier (or mixed) must still flag approximate=True so
    # an agent never overstates precision to the user.
    for model in ("moshier", "mixed"):
        out = attach_run_metadata(
            {
                "chart_profile": {
                    "engine_backend": "swisseph_api",
                    "engine_precision": "ephemeris_runtime_model",
                    "ephemeris_model": model,
                }
            },
            tool_name="astro_chart",
        )
        assert out["run_metadata"]["engine_is_approximate"] is True, model
    # Full Swiss Ephemeris data files present -> genuine full precision.
    swieph = attach_run_metadata(
        {
            "chart_profile": {
                "engine_backend": "swisseph_api",
                "engine_precision": "ephemeris_runtime_model",
                "ephemeris_model": "swieph",
            }
        },
        tool_name="astro_chart",
    )
    assert swieph["run_metadata"]["engine_is_approximate"] is False


def test_engine_is_approximate_unit() -> None:
    assert engine_is_approximate("approximate_orbital_model") is True
    assert engine_is_approximate("mixed_runtime_backends") is True
    assert engine_is_approximate("ephemeris_runtime_model") is False
    assert engine_is_approximate(run_metadata.DEFAULT_ENGINE) is False


def test_attach_run_metadata_is_idempotent() -> None:
    seeded = {"run_metadata": {"tool_name": "already"}, "x": 1}
    assert attach_run_metadata(seeded, tool_name="other") is seeded


def test_resolve_runtime_engine_still_detects_engine() -> None:
    assert (
        resolve_runtime_engine({"chart_profile": {"engine_backend": "swiss"}})
        == "swiss"
    )
    assert resolve_runtime_engine({"nothing": 1}) == run_metadata.DEFAULT_ENGINE


def test_native_response_preserves_the_tool_receipt_without_duplicate_text() -> None:
    spec = SPECS["gua_lookup"]
    result = asyncio.run(native(spec, {"queries": ["111111"]}))
    assert not result.is_error
    payload = result.structured_content
    assert payload["run_metadata"]["tool_name"] == spec.name
    assert payload["run_metadata"]["run_id"]
    assert result.content == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"queries": ["111", "000"]},
        {"queries": ["111"], "fields": ["missing"]},
    ],
)
def test_native_success_and_error_use_structured_content(arguments) -> None:
    async def run():
        async with Client(cached_mcp_app(families="divination")) as client:
            result = await call_calculation(
                client, "gua_lookup", arguments, raise_on_error=False
            )
            payload = result.structured_content
            assert result.is_error is ("error_code" in payload)
            if result.is_error:
                assert result.content[0].text == payload["error"]
            else:
                assert result.content == []
                assert "snapshot_text" not in payload

    asyncio.run(run())


def test_mcp_import_inside_running_loop_has_no_coroutine_warning() -> None:
    code = """
import asyncio, gc, warnings
warnings.simplefilter('error', RuntimeWarning)
async def load():
    from fastmcp import Client
    import fatebridge.mcp_server as module
    async with Client(module.app) as client:
        assert any(tool.name == 'run_calculation' for tool in await client.list_tools())
    gc.collect()
asyncio.run(load())
"""
    proc = subprocess.run(
        [sys.executable, "-W", "error::RuntimeWarning", "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "never awaited" not in proc.stderr


def test_classical_rules_import_without_predictive_backend() -> None:
    code = """
import sys
from fatebridge.core.classical_western import bound_lord
assert bound_lord('Aries', 0.0) == 'Jupiter'
assert 'fatebridge.core.predictive._common' not in sys.modules
"""
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr


def test_invalid_or_missing_trigram_is_not_replaced_by_a_default() -> None:
    base = {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"}
    with pytest.raises(ValueError, match="taiyin"):
        build_tongshefa_result()
    with pytest.raises(ValueError, match="taiyin"):
        build_tongshefa_result(taiyin=None, taiyang=None, shaoyang=None, shaoyin=None)
    for field in ("taiyin", "taiyang", "shaoyang", "shaoyin"):
        partial = {k: v for k, v in base.items() if k != field}
        with pytest.raises(ValueError, match=field):
            build_tongshefa_result(**partial)
        for invalid in (None, "乾卦", ""):
            with pytest.raises(ValueError, match=field):
                build_tongshefa_result(**{**base, field: invalid})


def test_empty_and_invalid_trigrams_fail_on_all_transports(rest, surface_calls) -> None:
    spec = SPECS["combine_four_gua"]
    valid = {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"}

    response, protocol, code, local = surface_calls(spec, {})
    assert response.status_code == 422 and code == 2 and protocol.is_error
    for output in (response.json(), protocol.structured_content):
        assert output["error_code"] == "validation_error"
        assert "tongshefa" not in output
        assert {issue["path"] for issue in output["issues"]} == set(valid)
    assert local["error_code"] == "usage_error"
    assert "tongshefa" not in local
    for field in valid:
        assert f"--{field}" in local["error"]

    for field in ("taiyin", "taiyang", "shaoyang", "shaoyin"):
        payload = {**valid, field: "乾卦"}
        if field == "taiyin":
            response, protocol, code, local = surface_calls(spec, payload)
            assert response.status_code == 422 and code == 1 and protocol.is_error
            outputs = (response.json(), local, protocol.structured_content)
        else:
            response = rest.post(spec.rest_path, json=payload)
            assert response.status_code == 422
            outputs = (response.json(),)
        for output in outputs:
            assert output["error_code"] == "validation_error"
            assert any(issue["path"] == field for issue in output["issues"])
            assert "tongshefa" not in output


def test_explicit_trigrams_build_expected_tongshefa_chart(rest, surface_calls) -> None:
    payload = {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"}
    result = build_tongshefa_result(**payload)
    assert result["analysis_context"] == payload
    assert result["tongshefa"]["baseLeft"]["name"] == "风雷益"
    assert result["tongshefa"]["baseRight"]["name"] == "地雷复"
    response, protocol, code, local = surface_calls(SPECS["combine_four_gua"], payload)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert local["tongshefa"]["baseLeft"]["name"] == "风雷益"
