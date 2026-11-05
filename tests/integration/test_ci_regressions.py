"""Related contract regressions with shared imports; original cases retained."""

import asyncio
import json
import math
import os
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import fatebridge.mcp_server as mcp
from fatebridge.api import app as rest_app
from fatebridge.application.result_delivery import bound_response
from fatebridge.core import almanac, moshier_solar, solar_term_clock
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import ephemeris_call, swe
from fatebridge.core.local_techniques.chart import _resolve_coordinates
from fatebridge.core.local_techniques.tongshefa import build_tongshefa_result
from fatebridge.core.metaphysics.ren_calendar import require_ren_solar_term
from fatebridge.mcp_server import create_mcp_app
from fatebridge.mcp_transport import OutputFlags
from fatebridge.services import run_metadata
from fatebridge.services.run_metadata import (
    attach_run_metadata,
    engine_is_approximate,
    resolve_runtime_engine,
)
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import EphemerisSourceError, ParameterError
from fatebridge.utils.private_files import (
    _windows_user,
    ensure_private_directory,
    locked_private_file,
    open_private_file,
)
from tests.support.output_facts import canonical_json
from tests.support.transports import SPECS, native, rest, surface_calls


@pytest.mark.parametrize(
    "value,axis,expected",
    [
        (0, "longitude", 0),
        (0, "latitude", 0),
        ("121e30", "longitude", 121.5),
        ("31s15", "latitude", -31.25),
        ("-180", "longitude", -180),
        ("90N0", "latitude", 90),
        (None, "latitude", None),
        ("", "longitude", None),
    ],
)
def test_decimal_and_direction_coordinates(value, axis, expected):
    assert parse_geo_coordinate(value, axis=axis) == expected


@pytest.mark.parametrize(
    "value,axis",
    [
        ("31N90", "latitude"),
        ("190", "longitude"),
        (-91, "latitude"),
        (float("nan"), "longitude"),
        (float("inf"), "latitude"),
        ("31E13", "latitude"),
        ("121N28", "longitude"),
        ("bad", "longitude"),
        ("-31N0", "latitude"),
        (True, "latitude"),
    ],
)
def test_invalid_coordinates_never_fall_back_to_a_default(value, axis):
    with pytest.raises(ValueError):
        parse_geo_coordinate(value, axis=axis)


@pytest.mark.parametrize("latitude,longitude", [(0, 0), (0, 32.5), (51.5, 0)])
def test_zero_coordinates_are_preserved(latitude, longitude):
    assert _resolve_coordinates(gps_lat=latitude, gps_lon=longitude) == (
        latitude,
        longitude,
    )


def test_gps_coordinates_take_precedence_over_text_hints():
    assert _resolve_coordinates(lat="bad", lon="bad", gps_lat=0, gps_lon=0) == (0, 0)


@pytest.mark.parametrize(
    "key,options",
    [
        ("sixyao", {"method": "time"}),
        ("sixyao", {"method": "coin", "seed": 42}),
        ("sixyao", {"coins": [6, 7, 8, 9, 7, 8]}),
        ("sixyao", {"gua_code": "111111"}),
        ("sanshiunited", {}),
    ],
)
@pytest.mark.parametrize("clock", ["", "   "])
def test_empty_required_clock_fails_on_every_transport(
    key, options, clock, surface_calls
):
    spec = SPECS[key]
    payload = {"date": "2026-02-10", "time": clock, **options}
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert "time" in output["error"]
        assert "run_metadata" not in output


@pytest.mark.parametrize("year", [1799, 1800, 2200, 2201])
def test_all_original_native_events_select_the_first_post_crossing_point(
    year, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term, target in zip(terms, almanac.SOLAR_TERM_LONGITUDES, strict=True):
        details = term.solar_model_details
        point = details["selected_crossing_jd_tt"]
        before = math.nextafter(point, -math.inf)
        assert term.resolution_provider == moshier_solar.PROVIDER
        assert term.ephemeris_model == moshier_solar.MODEL_ID
        left = moshier_solar.solar_longitude(before)
        right = moshier_solar.solar_longitude(point)
        assert math.remainder(left - target, 360) < 0, term.name
        assert math.remainder(right - target, 360) >= 0, term.name
        assert details["root_bracket_tt"] == [before, point]
        assert details["root_selection_policy"] == "first_post_crossing_tt_float"
        assert ephemeris_time(term.moment).jd_tt == point
        assert details["accuracy_certified"] is False
        require_ren_solar_term(term)


def test_exact_crossing_at_the_first_scan_sample_is_not_lost(monkeypatch):
    anchor = datetime(2000, 6, 1, tzinfo=timezone.utc)
    root = ephemeris_time(anchor).jd_tt - 30.0

    def linear_sun(operation, point, body, flags):
        assert operation == "calc" and body == swe.SUN
        return ((point - root) % 360, 0, 1, 1, 0, 0), swe.FLG_MOSEPH

    monkeypatch.setattr(almanac, "ephemeris_call", linear_sun)
    monkeypatch.setattr(
        moshier_solar, "solar_longitude", lambda point: (point - root) % 360
    )
    provenance = {}
    moment = almanac._solar_term_utc_via_swe(2000, 0, anchor, provenance)
    assert moment is not None
    assert provenance["resolved_jd_tt"] == root
    assert ephemeris_time(moment).jd_tt == root


def test_new_post_crossing_contract_rejects_a_coherent_pre_crossing_point(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    term = almanac.get_solar_terms_for_year(2026, "UTC")[0]
    details = dict(term.solar_model_details)
    low = details["root_bracket_tt"][0]
    details["selected_crossing_jd_tt"] = low
    bad = replace(
        term,
        moment=solar_term_clock.native_solar_root_datetime(low),
        solar_model_details=details,
    )
    with pytest.raises(EphemerisSourceError) as caught:
        require_ren_solar_term(bad)
    assert caught.value.reason == "ren_solar_term_longitude_inconsistent"

    # A retired model name cannot bypass the current crossing contract.
    historical = dict(details)
    historical["model_id"] = "native_swiss_tt_solar_bisection_v1"
    historical.pop("root_selection_policy")
    with pytest.raises((EphemerisSourceError, RuntimeError)):
        require_ren_solar_term(replace(bad, solar_model_details=historical))


def test_current_facts_ignore_only_execution_receipts():
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
def test_nonfinite_current_facts_are_rejected(value):
    with pytest.raises(ValueError):
        canonical_json({"coordinate": value})


@pytest.mark.parametrize("fail", [False, True])
def test_windows_token_is_closed_without_assuming_a_context_manager(monkeypatch, fail):
    closed = []
    token = SimpleNamespace(Close=lambda: closed.append(True))

    def information(handle, kind):
        assert handle is token and kind == "user"
        if fail:
            raise OSError("token query failed")
        return ("sid",)

    monkeypatch.setitem(
        sys.modules, "win32api", SimpleNamespace(GetCurrentProcess=lambda: "process")
    )
    monkeypatch.setitem(sys.modules, "win32con", SimpleNamespace(TOKEN_QUERY="query"))
    monkeypatch.setitem(
        sys.modules,
        "win32security",
        SimpleNamespace(
            OpenProcessToken=lambda process, access: token,
            GetTokenInformation=information,
            TokenUser="user",
        ),
    )
    if fail:
        with pytest.raises(OSError, match="token query failed"):
            _windows_user()
    else:
        assert _windows_user() == "sid"
    assert closed == [True]


def test_threads_cannot_enter_the_same_artifact_lock_together(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    started, acquired = threading.Event(), threading.Event()
    errors = []

    def read():
        started.set()
        try:
            with locked_private_file(directory / ".lock"):
                acquired.set()
        except Exception as exc:
            errors.append(exc)

    with locked_private_file(directory / ".lock"):
        thread = threading.Thread(target=read)
        thread.start()
        assert started.wait(5)
        assert not acquired.wait(0.1)
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors
    assert acquired.is_set()


def test_new_files_are_private_and_exclusive_creation_never_replaces_them(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    path = directory / "result"
    fd = open_private_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as handle:
        handle.write(b"private result")
    with pytest.raises(OSError):
        open_private_file(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    assert path.read_bytes() == b"private result"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_world_readable_directory_and_file_are_rejected(tmp_path):
    directory = ensure_private_directory(tmp_path / "private")
    path = directory / "result"
    path.write_bytes(b"secret")
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="private"):
        open_private_file(path, os.O_RDONLY)
    directory.chmod(0o755)
    with pytest.raises(RuntimeError, match="private"):
        ensure_private_directory(directory)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows ACL")
def test_windows_rejects_directory_with_an_everyone_read_ace(tmp_path):
    import win32con
    import win32security

    directory = ensure_private_directory(tmp_path / "private")
    descriptor = win32security.GetFileSecurity(
        str(directory), win32security.DACL_SECURITY_INFORMATION
    )
    acl = descriptor.GetSecurityDescriptorDacl()
    acl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        win32con.GENERIC_READ,
        win32security.CreateWellKnownSid(win32security.WinWorldSid, None),
    )
    win32security.SetNamedSecurityInfo(
        str(directory),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )
    with pytest.raises(RuntimeError, match="private"):
        ensure_private_directory(directory)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows junction")
def test_windows_never_uses_a_junction_as_the_result_directory(tmp_path):
    outside = ensure_private_directory(tmp_path / "outside")
    junction = tmp_path / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
    )
    try:
        with pytest.raises(OSError, match="reparse"):
            ensure_private_directory(junction)
    finally:
        junction.rmdir()


def test_domain_requests_build_nested_schemas():
    code = """
from fatebridge.core.requests.divination import SixYaoRequest
from fatebridge.core.requests.astrology import AstroRelativeRequest
sixyao = SixYaoRequest.model_validate({'date': '2028-01-01', 'time': '00:00:00',
    'lines': [{'value': 1, 'change': True}] + [{'value': 0, 'change': False}] * 5})
assert len(sixyao.lines) == 6
assert sixyao.lines[0].value == 1 and sixyao.lines[0].change
assert 'SixYaoLineRequest' in SixYaoRequest.model_json_schema()['$defs']
assert 'AstroRelativePartyRequest' in AstroRelativeRequest.model_json_schema()['$defs']
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_catalog_cold_import_does_not_load_domain_engines():
    code = """
import sys
from fatebridge.services.tool_catalog import CATALOG
assert len({spec.key for spec in CATALOG}) == len(CATALOG)
for module in ('kerykeion', 'fatebridge.services.bazi',
               'fatebridge.services.astrology', 'fatebridge.services.western_timing'):
    assert module not in sys.modules, module
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_rest_mcp_flags_and_renderer_agree_on_disjoint_response_budget():
    async def schema():
        async with Client(create_mcp_app(families="bazi")) as client:
            tools = await client.list_tools()
            career = next(tool for tool in tools if tool.name == "bazi_career")
            return career.model_dump(by_alias=True)["inputSchema"]["properties"][
                "response_char_limit"
            ]

    mcp_schema = asyncio.run(schema())
    rest_schema = next(
        parameter["schema"]
        for parameter in rest_app.openapi()["paths"]["/api/cn/bazi/career"]["post"][
            "parameters"
        ]
        if parameter["name"] == "response_char_limit"
    )
    validators = [Draft202012Validator(s) for s in (rest_schema, mcp_schema)]
    for value in [0, 4096, 8192, 65536]:
        assert all(validator.is_valid(value) for validator in validators)
        assert OutputFlags(response_char_limit=value).response_char_limit == value
        assert bound_response({"status": "small"}, value) == {"status": "small"}
    for value in [-1, 1, 4095, 65537]:
        assert not any(validator.is_valid(value) for validator in validators)
        with pytest.raises(ValidationError):
            OutputFlags(response_char_limit=value)
        with pytest.raises(ParameterError):
            bound_response({"status": "small"}, value)


def test_explicit_zero_http_budget_and_invalid_budget_before_execution(monkeypatch):
    import fatebridge.api as api
    from fatebridge.application.examples import example_input
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.transports import rest

    spec = next(spec for spec in CATALOG if spec.key == "bazi_career")
    inputs = example_input(spec)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    for value in [0, 4096, 65536]:
        response = client.post(
            spec.rest_path, json=inputs, params={"response_char_limit": value}
        )
        assert response.status_code == 200, response.json()
        assert "error" not in response.json()
        if value == 0:
            assert "career_analysis" in response.json()
            assert "result_delivery" not in response.json()

    def must_not_execute(*args, **kwargs):
        pytest.fail("invalid HTTP budget must fail before domain execution")

    monkeypatch.setattr(rest, "execute_tool", must_not_execute)
    for value in [1, 4095, 65537, "invalid"]:
        response = client.post(
            spec.rest_path, json=inputs, params={"response_char_limit": value}
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "validation_error"


def test_attach_run_metadata_uses_explicit_name():
    out = attach_run_metadata({"x": 1}, tool_name="bazi_wealth")
    assert out["run_metadata"]["tool_name"] == "bazi_wealth"


def test_run_metadata_flags_approximate_astro_engine():
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


def test_run_metadata_flags_silent_moshier_downgrade():
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


def test_engine_is_approximate_unit():
    assert engine_is_approximate("approximate_orbital_model") is True
    assert engine_is_approximate("mixed_runtime_backends") is True
    assert engine_is_approximate("ephemeris_runtime_model") is False
    assert engine_is_approximate(run_metadata.DEFAULT_ENGINE) is False


def test_attach_run_metadata_is_idempotent():
    seeded = {"run_metadata": {"tool_name": "already"}, "x": 1}
    assert attach_run_metadata(seeded, tool_name="other") is seeded


def test_resolve_runtime_engine_still_detects_engine():
    assert (
        resolve_runtime_engine({"chart_profile": {"engine_backend": "swiss"}})
        == "swiss"
    )
    assert resolve_runtime_engine({"nothing": 1}) == run_metadata.DEFAULT_ENGINE


def test_render_does_not_guess_tool_name_from_payload_shape():
    from fatebridge.mcp_server import _render_protocol_response

    # A payload whose shape the OLD guesser would have mapped to "chart13".
    misleading = {"chart_profile": {"chart_type": "chart13"}}
    rendered = _render_protocol_response(misleading, tool_name=None)
    payload = rendered.structured_content
    # No explicit name supplied -> a neutral marker, NOT a shape-derived guess.
    assert payload["run_metadata"]["tool_name"] == "unknown_tool"


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": ["111", "000"], "compact": False, "include_snapshot_text": False},
        {"name": ["111"], "fields": ["missing"], "strict_fields": True},
    ],
)
def test_native_success_and_error_have_matching_text_and_structured_content(arguments):
    async def run():
        async with Client(mcp.create_mcp_app(families="divination")) as client:
            result = await client.call_tool(
                "gua_meiyi", arguments, raise_on_error=False
            )
            payload = json.loads(result.content[0].text)
            assert payload == result.structured_content
            assert result.is_error is ("error_code" in payload)
            if not arguments.get("strict_fields"):
                assert "\n" in result.content[0].text
                assert "snapshot_text" not in payload

    asyncio.run(run())


def test_mcp_import_inside_running_loop_has_no_coroutine_warning():
    code = """
import asyncio, gc, warnings
warnings.simplefilter('error', RuntimeWarning)
async def load():
    from fastmcp import Client
    import fatebridge.mcp_server as module
    async with Client(module.app) as client:
        assert any(tool.name == 'gua_meiyi' for tool in await client.list_tools())
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


def test_classical_rules_import_without_predictive_backend():
    code = """
import sys
from fatebridge.core.classical_western import bound_lord
assert bound_lord('Aries', 0.0) == 'Jupiter'
assert 'fatebridge.core.predictive._common' not in sys.modules
assert 'kerykeion' not in sys.modules
"""
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("field", ["taiyin", "taiyang", "shaoyang", "shaoyin"])
@pytest.mark.parametrize("invalid", ["乾卦", ""])
def test_invalid_trigram_is_not_replaced_by_a_default(field, invalid):
    with pytest.raises(ValueError, match=field):
        build_tongshefa_result(**{field: invalid})


@pytest.mark.parametrize("field", ["taiyin", "taiyang", "shaoyang", "shaoyin"])
def test_invalid_trigram_fails_on_all_transports(field, surface_calls):
    spec = SPECS["tongshefa"]
    payload = {field: "乾卦"}
    response, protocol, code, local = surface_calls(spec, payload)
    assert response.status_code == 400 and code == 1 and protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        assert output["error_code"] == "validation_error"
        assert field in output["error"]
        assert "tongshefa" not in output


def test_omitted_and_null_trigrams_keep_the_declared_default_chart():
    result = build_tongshefa_result(
        taiyin=None, taiyang=None, shaoyang=None, shaoyin=None
    )
    assert result["input_normalized"] == {
        "taiyin": "巽",
        "taiyang": "坤",
        "shaoyang": "震",
        "shaoyin": "震",
    }
    assert result["tongshefa"]["baseLeft"]["name"] == "风雷益"
    assert result["tongshefa"]["baseRight"]["name"] == "地雷复"
