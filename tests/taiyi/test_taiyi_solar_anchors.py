"""A native-library provider alone does not identify its actual orbit model."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from tests.taiyi.test_taiyi_transports import _same_run_payload

PROFILES = [
    ("month", None),
    ("month", "key_month_tianzheng_jie_v1"),
    ("day", None),
    ("hour", None),
    ("hour", "key_hour_winter_jiazi_v1"),
]


@pytest.fixture(autouse=True)
def controlled_moshier(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))


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
    return dict(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options=selected,
    )


@pytest.mark.parametrize("mode,profile", PROFILES)
@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
def test_all_source_anchor_profiles_keep_same_run_models_and_text(tool, mode, profile):
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
        assert value["resolution_provider"] == "swisseph"
        assert value["ephemeris_model"] == "moshier"
        assert value["solar_model_details"]["root_time_scale"] == "TT"
        assert "swisseph/moshier" in result["snapshot_text"]
    assert anchors["boundary"]["name"] == board["calendar_rules"]["anchor_name"]
    assert (
        anchors["boundary"]["datetime_with_offset"]
        == board["calendar_rules"]["anchor_utc"]
    )
    assert board["calendar_summary"]["anchor_ephemeris_model"] == "moshier"
    assert (
        "winter_anchor_ephemeris_model" in board["calendar_summary"]
    ) == winter_expected
    assert result["snapshot_text"].count("节气实际模型：") == 1
    assert result["snapshot_export"]["export_text"].count("节气实际模型：") == 1
    if tool == "sanshiunited":
        assert (
            result["subresults"]["taiyi"]["pan"]["calendar_rules"]
            == board["calendar_rules"]
        )


def test_source_record_mutation_cannot_poison_the_cached_term():
    args = inputs("taiyi", "day", None)
    first = calculate_taiyi_analysis(**args)
    expected = deepcopy(first["taiyi"]["solar_anchors"])
    for value in first["taiyi"]["solar_anchors"].values():
        value["solar_model_details"]["selected_crossing_jd_tt"] = -1
    second = calculate_taiyi_analysis(**args)
    assert second["taiyi"]["solar_anchors"] == expected


def test_year_count_does_not_invent_an_unused_solar_anchor():
    result = calculate_taiyi_analysis(**inputs("taiyi", "year", None))
    assert "solar_anchors" not in result["taiyi"]
    assert "anchor_ephemeris_model" not in result["taiyi"]["calendar_summary"]
    assert "节气实际模型：" not in result["snapshot_text"]


@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize(
    "mode,profile", [("day", None), ("hour", "key_hour_winter_jiazi_v1")]
)
def test_actual_rest_mcp_cli_and_same_run_source_view(
    tool, mode, profile, monkeypatch, capsys
):
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
    argv = [tool, "--strict-fields", "--no-include-snapshot-text", "--fields", *fields]
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
            response = await client.call_tool(
                spec.mcp_name,
                {
                    **values,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            full = await _same_run_payload(client, response)
            assert full["taiyi"] == expected

    asyncio.run(call())


def test_actual_native_moshier_anchor_reaches_the_same_board(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
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
    assert anchors["boundary"]["resolution_provider"] == "swisseph"
    assert anchors["boundary"]["ephemeris_model"] == "moshier"
    assert anchors["winter_origin"]["ephemeris_model"] == "moshier"
    assert board["calendar_summary"]["anchor_ephemeris_model"] == "moshier"
