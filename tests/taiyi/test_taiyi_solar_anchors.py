"""A native-library provider alone does not identify its actual orbit model."""

import asyncio
import json
from copy import deepcopy

import pytest
import swisseph as swe
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.contracts.output_chinese import Taiyi
from fatebridge.core.ephemeris_runtime import ephemeris_call
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation
from tests.unit_test.fixtures.taiyi import same_run_payload

PROFILES = [
    ("month", None),
    ("month", "key_month_tianzheng_jie_v1"),
    ("day", None),
    ("hour", None),
    ("hour", "key_hour_winter_jiazi_v1"),
]
FALLBACK_PROVIDER = "jpl_de441"
FALLBACK_MODEL = "fatebridge_de441_solar_v1"


@pytest.fixture(autouse=True)
def controlled_de441_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def options(mode, profile):
    return {
        "calculation_mode": mode,
        **(
            {("hour_profile" if mode == "hour" else "month_profile"): profile}
            if profile
            else {}
        ),
    }


def inputs(tool, mode, profile):
    selected = options(mode, profile)
    if tool == "taiyi":
        return dict(
            analysis_year=2026,
            analysis_month=10,
            analysis_day=25,
            analysis_hour=12,
            analysis_timezone="+08:00",
            use_true_solar_time=False,
            **selected,
        )
    else:
        pass
    return dict(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options=selected,
    )


@pytest.mark.parametrize("mode,profile", PROFILES)
@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
def test_all_source_anchor_profiles_keep_same_run_models_and_text(
    tool: str, mode, profile
) -> None:
    fn = (
        calculate_taiyi_analysis if tool == "taiyi" else calculate_sanshiunited_analysis
    )
    result = fn(**inputs(tool, mode, profile))
    board = result["taiyi"]
    Taiyi.model_validate(board)
    anchors = board["solar_anchors"]
    winter_expected = mode == "day" or profile == "key_hour_winter_jiazi_v1"
    assert set(anchors) == (
        {"boundary", "winter_origin"} if winter_expected else {"boundary"}
    )
    for value in anchors.values():
        assert value["resolution_provider"] == FALLBACK_PROVIDER
        assert value["ephemeris_model"] == FALLBACK_MODEL
        assert value["solar_model_details"]["root_time_scale"] == "TT"
        assert f"{FALLBACK_PROVIDER}/{FALLBACK_MODEL}" in result["snapshot_text"]
    assert anchors["boundary"]["name"] == board["calendar_rules"]["anchor_name"]
    assert (
        anchors["boundary"]["datetime_with_offset"]
        == board["calendar_rules"]["anchor_utc"]
    )
    assert board["calendar_summary"]["anchor_ephemeris_model"] == FALLBACK_MODEL
    assert (
        "winter_anchor_ephemeris_model" in board["calendar_summary"]
    ) == winter_expected
    assert result["snapshot_text"].count("节气实际模型：") == 1
    assert result["snapshot_export"]["export_text"].count("节气实际模型：") == 1


def test_source_record_mutation_cannot_poison_the_cached_term() -> None:
    args = inputs("taiyi", "day", None)
    first = calculate_taiyi_analysis(**args)
    expected = deepcopy(first["taiyi"]["solar_anchors"])
    for value in first["taiyi"]["solar_anchors"].values():
        value["solar_model_details"]["selected_crossing_jd_tt"] = -1
    second = calculate_taiyi_analysis(**args)
    assert second["taiyi"]["solar_anchors"] == expected


def test_year_count_does_not_invent_an_unused_solar_anchor() -> None:
    result = calculate_taiyi_analysis(**inputs("taiyi", "year", None))
    assert "solar_anchors" not in result["taiyi"]
    assert "anchor_ephemeris_model" not in result["taiyi"]["calendar_summary"]
    assert "节气实际模型：" not in result["snapshot_text"]


@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "mode,profile", [("day", None), ("hour", "key_hour_winter_jiazi_v1")]
)
def test_actual_rest_mcp_cli_and_same_run_source_view(
    tool: str,
    mode: str,
    profile: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = next(s for s in CATALOG if s.key == tool)
    values = inputs(tool, mode, profile)
    fields = suggested_fields(spec, view="solar_anchors")
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        r = client.post(
            spec.rest_path,
            json=values,
            params=[("fields", f) for f in fields]
            + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        )
    assert r.status_code == 200, r.text
    expected = r.json()["taiyi"]
    argv = [
        spec.tool_name,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    for key, value in values.items():
        if key == "use_true_solar_time":
            argv.append("--no-use-true-solar-time")
        else:
            argv += [
                "--" + key.replace("_", "-"),
                json.dumps(value) if isinstance(value, dict) else str(value),
            ]
    assert run(argv) == 0
    assert json.loads(capsys.readouterr().out)["taiyi"] == expected

    async def call():
        async with Client(create_mcp_app()) as client:
            response = await call_calculation(
                client,
                spec.mcp_name,
                {
                    **values,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            full = await same_run_payload(client, response)
            assert full["taiyi"] == expected

    asyncio.run(call())


def test_native_moshier_probe_selects_the_de441_calendar_anchor() -> None:
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=25,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode="day",
    )
    board = result["taiyi"]
    assert "solar_anchors" in board
    anchors = board["solar_anchors"]
    boundary = anchors["boundary"]
    _, native_flags = ephemeris_call(
        "calc",
        boundary["solar_model_details"]["selected_crossing_jd_tt"],
        swe.SUN,
        swe.FLG_SWIEPH,
    )
    assert native_flags == swe.FLG_MOSEPH
    assert boundary["resolution_provider"] == FALLBACK_PROVIDER
    assert boundary["ephemeris_model"] == FALLBACK_MODEL
    assert boundary["solar_model_details"]["native_moshier_relabelled"] is False
    assert anchors["winter_origin"]["ephemeris_model"] == FALLBACK_MODEL
    assert board["calendar_summary"]["anchor_ephemeris_model"] == FALLBACK_MODEL
