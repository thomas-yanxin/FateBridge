"""The native Guolao solar clock must not depend on an unused legacy display."""

import asyncio
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import guolao, guolao_timing
from fatebridge.core.astro import birth as birth_module
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.test_guolao_native_frames import fixed_moshier  # noqa: F401

FIXTURE = Path(__file__).parent / "fixtures/guolao-same-sky-construction-v1"
HELD = json.loads(
    (Path(__file__).parent / "data/guolao/year_edge_inputs.json").read_bytes()
)
CASE = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=15.761059045869185,
    birth_latitude=40,
)


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize(
    "solar,policy",
    [
        (False, None),
        (True, None),
        (True, "source_solar_days_winter_exclusive"),
        (True, "source_solar_days_winter_inclusive"),
    ],
)
def test_same_sky_clock_remains_usable_when_unused_legacy_display_is_unavailable(
    monkeypatch, fixed_moshier, solar, policy, zodiacal
):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise ValueError("unused legacy display unavailable")

    monkeypatch.setattr(birth_module, "calculate_solar_time_adjustment", forbidden)
    result = calculate_core_chart_analysis(
        **CASE,
        chart_variant="guolao_chart",
        use_true_solar_time=solar,
        zodiacal=zodiacal,
        guolao_seasonal_anchor_policy=policy,
    )
    assert "error" not in result, result
    assert not calls
    assert result["person_info"]["utc_datetime"] == "2000-01-01T00:00:00+00:00"
    assert result["person_info"]["true_solar"]["applied"] is solar
    assert result["guolao"]["life_palace"]["birth_hour_branch"] == (
        "丑" if solar else "子"
    )
    if solar:
        clock = result["guolao"]["profile"]["apparent_solar_clock"]
        assert (
            clock["birth_hour_branch"]
            == result["guolao"]["life_palace"]["birth_hour_branch"]
        )
        assert clock["julian_day_ut1"] == result["guolao"]["profile"]["julian_day_ut1"]
    assert not result["guolao"]["validation"]["full_marks_established"]


@pytest.mark.parametrize("row_index", range(6))
def test_range_boundary_keeps_valid_outputs_and_computes_unrepresentable_utc_label(
    fixed_moshier, row_index
):
    held = HELD[row_index]
    result = calculate_core_chart_analysis(**held["input"])
    assert "error" not in result, result
    if row_index != 3:
        assert result["guolao"]["validation"]["full_marks_established"] is False
        return
    # Independent calendar arithmetic: local Jan1 at+14 is preceding Dec31
    # 10:00. The astronomical year0 label is not a Python datetime or a record.
    assert result["person_info"]["utc_datetime"] == "0000-12-31T10:00:00+00:00"
    civil = calculate_core_chart_analysis(
        **{**held["input"], "use_true_solar_time": False}
    )
    assert "error" not in civil
    assert result["guolao"]["bodies"] == civil["guolao"]["bodies"]
    assert (
        result["guolao"]["mansion_boundaries"] == civil["guolao"]["mansion_boundaries"]
    )
    clock = result["guolao"]["profile"]["apparent_solar_clock"]
    assert (
        clock["display"] is None
        and clock["display_status"] == "outside_datetime_year_range"
    )
    assert result["guolao"]["life_palace"]["birth_hour_branch"] == "亥"
    assert result["guolao"]["life_palace"]["birth_clock"] is None
    assert result["guolao"]["life_palace"]["clock_basis"] == "apparent_solar_display"


@pytest.mark.parametrize("variant", ["chart", "chart13", "hellen_chart", "germany"])
def test_other_legacy_consumers_are_not_silently_rebased_or_ignored(
    monkeypatch, fixed_moshier, variant
):
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(True)
        raise ValueError("required legacy clock unavailable")

    from fatebridge.core.astro import solar_rebase

    monkeypatch.setattr(solar_rebase, "calculate_solar_time_adjustment", unavailable)
    result = calculate_core_chart_analysis(
        **CASE, chart_variant=variant, use_true_solar_time=True
    )
    assert "error" in result and calls


@pytest.mark.parametrize(
    "case_name", ["modern", "utc_year0", "utc0_target", "utc0_jie", "utc0_lunar"]
)
@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("physical_failure", [False, True])
def test_actual_three_surfaces_skip_unused_display_and_keep_physical_errors(
    monkeypatch,
    fixed_moshier,
    capsys,
    record_testsuite_property,
    case_name,
    tool,
    solar,
    physical_failure,
):
    def unused(*args, **kwargs):
        pytest.fail("Guolao construction must not execute legacy display")

    monkeypatch.setattr(birth_module, "calculate_solar_time_adjustment", unused)
    if physical_failure:
        native = guolao.runtime.ephemeris_call

        def failed(operation, *args, **kwargs):
            if operation == "calc" and args[1] == guolao.runtime.swe.SUN:
                raise EphemerisSourceError("coordinate_values_unavailable")
            return native(operation, *args, **kwargs)

        monkeypatch.setattr(guolao.runtime, "ephemeris_call", failed)
    spec = next(s for s in CATALOG if s.key == tool)
    payload = dict(**CASE, use_true_solar_time=solar)
    if case_name != "modern":
        payload.update(
            birth_year=1,
            birth_month=1,
            birth_day=1,
            birth_hour=0,
            birth_timezone="+14:00",
            birth_longitude=170,
        )
    if case_name == "utc0_target":
        payload["analysis_datetime"] = "0001-01-01T02:00:00+15:00"
    elif case_name in {"utc0_jie", "utc0_lunar"}:
        payload["analysis_datetime"] = "2027-06-01T00:00:00+08:00"
        payload["guolao_month_basis"] = (
            "jie_month" if case_name == "utc0_jie" else "chinese_lunar_utc8"
        )
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    options = dict(
        as_of="2026-10-25T00:00:00+08:00",
        include_snapshot_text=False,
        response_char_limit=0,
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params={
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in options.items()
        },
    )
    assert rest.status_code == (503 if physical_failure else 200), rest.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )
            assert result.is_error is physical_failure
            return (
                json.loads(result.content[0].text)
                if physical_failure
                else result.structured_content
            )

    mcp = asyncio.run(protocol())
    arguments = [spec.tool_name]
    for key, value in payload.items():
        arguments.extend(["--" + key.replace("_", "-"), str(value)])
    arguments.extend(
        [
            "--as-of",
            options["as_of"],
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ]
    )
    capsys.readouterr()
    assert run(arguments) == int(physical_failure)
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [rest.json(), mcp, cli]
    ]
    record_testsuite_property(
        f"wire-{case_name}-{tool}-{solar}-{physical_failure}",
        json.dumps(
            dict(rest_status=rest.status_code, rest=rest.json(), mcp=mcp, cli=cli),
            ensure_ascii=False,
        ),
    )
    if physical_failure:
        # REST deliberately projects ErrorEnvelope and puts status in HTTP.
        # Check the full declared mapping, rather than dropping unknown keys.
        assert bodies[2] == {**bodies[0], "status_code": rest.status_code}
        assert bodies[1] == {**bodies[2], "operation": spec.operation_label_zh}
        assert bodies[0]["error_code"] == "ephemeris_source_inconsistent"
        assert "guolao" not in bodies[0]
    else:
        assert bodies[0] == bodies[1] == bodies[2]
        assert bodies[0]["person_info"]["true_solar"]["applied"] is solar
        if case_name == "utc0_target":
            assert bodies[0]["guolao"]["timing"]["analysis_datetime"] == (
                "0000-12-31T11:00:00+00:00"
            )
        elif case_name in {"utc0_jie", "utc0_lunar"}:
            monthly = bodies[0]["guolao"]["timing"]["month_limit"]
            assert monthly["status"] == "unassigned_calendar_unavailable"
            assert monthly["branch"] is None


@pytest.mark.parametrize(
    "policy",
    [None, "source_solar_days_winter_exclusive", "source_solar_days_winter_inclusive"],
)
@pytest.mark.parametrize(
    "target,basis",
    [(False, None), (True, None), (True, "jie_month"), (True, "chinese_lunar_utc8")],
)
def test_optional_time_layers_preserve_sky_and_do_not_invent_unavailable_month(
    monkeypatch, fixed_moshier, policy, target, basis
):
    args = {
        **HELD[3]["input"],
        "guolao_seasonal_anchor_policy": policy,
    }
    if target:
        args["analysis_datetime"] = datetime.fromisoformat("2027-06-01T00:00:00+08:00")
    if basis:
        args["guolao_month_basis"] = basis
    result = calculate_core_chart_analysis(**args)
    assert "error" not in result, result
    g = result["guolao"]
    assert len(g["bodies"]) == 11
    assert g["life_palace"]["birth_hour_branch"] == "亥"
    if target:
        assert len(g["timing"]["transit_bodies"]) == 11
        assert g["timing"]["small_limit"]["branch"] is not None
    if basis:
        month = g["timing"]["month_limit"]
        assert month["birth_month"]["instant_utc"] == "0000-12-31T10:00:00+00:00"
        assert month["birth_month"]["status"] == "outside_datetime_calendar_range"
        assert month["status"] == "unassigned_calendar_unavailable"
        assert month["branch"] is month["natal_functional_palace"] is None
        assert month["event_probability_estimated"] is False
    assert g["validation"]["full_marks_established"] is False


def test_same_utc0_target_different_offsets_agree_and_earlier_target_rejects(
    fixed_moshier,
):
    args = HELD[3]["input"]
    results = [
        calculate_core_chart_analysis(
            **args, analysis_datetime=datetime.fromisoformat(t)
        )
        for t in ["0001-01-01T01:00:00+14:00", "0001-01-01T02:00:00+15:00"]
    ]
    assert "error" not in results[0] and "error" not in results[1]
    assert results[0] == results[1]
    timing = results[0]["guolao"]["timing"]
    assert timing["analysis_datetime"] == "0000-12-31T11:00:00+00:00"
    assert timing["calendar_datetime"] == "0001-01-01T01:00:00+14:00"
    earlier = calculate_core_chart_analysis(
        **args, analysis_datetime=datetime.fromisoformat("0001-01-01T00:00:00+15:00")
    )
    assert earlier["error"] == "果老目标时刻不能早于记录的出生时刻"
    assert "guolao" not in earlier


@pytest.mark.parametrize(
    "offset",
    [
        timedelta(hours=-23, minutes=-59),
        timedelta(hours=-12),
        timedelta(0),
        timedelta(hours=8),
        timedelta(hours=14),
        timedelta(hours=23, minutes=59),
        timedelta(seconds=27, microseconds=1),
    ],
)
def test_fixed_offset_calendar_conversion_matches_datetime_where_both_exist(offset):
    instant = datetime.fromisoformat("2026-01-01T01:02:03.456789+15:00")
    recorded = datetime(2000, 1, 1, tzinfo=timezone(offset))
    actual = guolao_timing._calendar_clock(instant, recorded)
    expected = instant.astimezone(recorded.tzinfo)
    assert actual.isoformat() == expected.isoformat()
