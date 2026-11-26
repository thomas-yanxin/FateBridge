"""Exercise actual REST, native in-process MCP and CLI for the same inputs."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_conditions import conjunction
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import SPECS, call_calculation


@pytest.mark.parametrize(
    "key,view",
    [
        ("taiyi", None),
        ("taiyi", "annual_cycles"),
        ("taiyi", "conditions"),
        ("taiyi", "enclosures"),
        ("taiyi", "oppositions"),
        ("taiyi", "counts"),
        ("taiyi", "count_sources"),
        ("taiyi", "shiji_derivation"),
        ("taiyi", "elemental_relations"),
        ("taiyi", "victory_matrix"),
        ("taiyi", "gates"),
        ("taiyi", "gate_comparison"),
        ("taiyi", "determinate"),
        ("sanshiunited", None),
        ("sanshiunited", "taiyi_depth"),
        ("sanshiunited", "palace_correspondences"),
        ("sanshiunited", "annual_cycles"),
        ("sanshiunited", "taiyi_conditions"),
        ("sanshiunited", "taiyi_enclosures"),
        ("sanshiunited", "taiyi_oppositions"),
        ("sanshiunited", "taiyi_counts"),
        ("sanshiunited", "taiyi_count_sources"),
        ("sanshiunited", "taiyi_shiji_derivation"),
        ("sanshiunited", "taiyi_elemental_relations"),
        ("sanshiunited", "taiyi_victory_matrix"),
        ("sanshiunited", "taiyi_gates"),
        ("sanshiunited", "taiyi_gate_comparison"),
        ("sanshiunited", "taiyi_determinate"),
    ],
)
@pytest.mark.parametrize(
    "mode,hour_profile,month_profile",
    [
        ("year", None, None),
        ("month", None, None),
        ("month", None, "key_month_tianzheng_jie_v1"),
        ("day", None, None),
        ("hour", None, None),
        ("hour", "key_hour_winter_jiazi_v1", None),
    ],
)
def test_published_first_views_preserve_evidence_under_default_limits(
    key: str,
    view: str | None,
    mode: str,
    hour_profile: str | None,
    month_profile: str | None,
) -> None:
    target_name = (
        "taiyi"
        if key == "taiyi"
        else ("sanshi_combined_chart" if key == "sanshiunited" else key)
    )
    spec = next(s for s in CATALOG if s.name == target_name)
    inputs = example_input(spec)
    assert inputs is not None
    if key == "taiyi":
        inputs["calculation_mode"] = mode
        if month_profile:
            inputs["month_profile"] = month_profile
        else:
            pass
        if hour_profile:
            inputs["hour_profile"] = hour_profile
        else:
            pass
    else:
        inputs["taiyi_options"] = {"calculation_mode": mode}
        if month_profile:
            inputs["taiyi_options"]["month_profile"] = month_profile
        else:
            pass
        if hour_profile:
            inputs["taiyi_options"]["hour_profile"] = hour_profile
        else:
            pass

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(
                client,
                spec.name,
                {
                    **inputs,
                    "detail": "audit",
                    "fields": suggested_fields(spec, view=view),
                },
                raise_on_error=False,
            )
            return result, result.structured_content

    result, body = asyncio.run(protocol())
    assert not result.is_error, result
    # Every requested business value was checked against the same-run archive.
    if view in {"conditions", "taiyi_conditions"}:
        assessment = body["taiyi"]["condition_assessment"]
        assert len(assessment["five_generals"]["clauses"]) == 3
        assert assessment["three_gates"]["status"] == (
            "not_assessed" if mode in {"hour", "day"} or month_profile else "computed"
        )

        assert assessment["menju_jiangfa"] is conjunction(
            assessment["five_generals"]["conditions_satisfied"],
            assessment["three_gates"].get("conditions_satisfied"),
        )
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
    elif view in {"counts", "taiyi_counts"}:
        assessed = body["taiyi"]["count_assessment"]
        assert len(assessed["entries"]) == 2 and len(assessed["sources"]) == 5
        assert assessed["overall_harmony_assessed"] is False
        assert len(assessed["unadjudicated_source_readings"]) == 2
    elif view in {"oppositions", "taiyi_oppositions"}:
        assessed = body["taiyi"]["opposition_assessment"]
        assert len(assessed["entries"]) == 6
        assert assessed["main_names_unified"] is False
        assert all(
            row["status"] in {"opposite", "not_opposite", "no_ring_bearing"}
            for row in assessed["entries"]
        )
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
    elif view in {"enclosures", "taiyi_enclosures"}:
        assessment = body["taiyi"]["enclosure_assessment"]
        assert assessment["principal_enclosure"]["status"] == "assessed_geometry"
        assert type(assessment["principal_enclosure"]["present"]) is bool
        assert {p["name"] for p in assessment["unassessed"]} == {
            "挟闭",
            "四郭固",
            "四郭杜",
        }
        assert {p["status"] for p in assessment["unassessed"]} == {"not_assessed"}
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is False
        assert "real_world_efficacy" not in body["taiyi"]["ruleset"]
    elif view in {"gates", "taiyi_gates", "gate_comparison", "taiyi_gate_comparison"}:
        gates = body["taiyi"]["gates"]
        if mode == "hour" and hour_profile is None:
            assert gates["status"] == "not_computed_for_selected_mode"
            assert gates["reason"] and gates["selected_profile"] is None
        else:
            assert gates["status"] == "computed"
            assert gates["selected_profile"]
    elif view in {"determinate", "taiyi_determinate"}:
        result = body["taiyi"]["determinate_calculation"]
        assert result["status"] == (
            "not_computed_for_selected_mode"
            if mode == "hour" and hour_profile is None
            else "computed"
        )
    elif view == "annual_cycles":
        cycles = body["taiyi"]["long_cycles"]
        assert cycles["time_granularity"] == "year"
        if mode == "year":
            assert len(cycles["records"]) == 11  # Ten markers plus 大游天目.
            assert cycles["ruleset"]["classical_acceptance_passed"] is False
        else:
            assert cycles["status"] == "not_computed_for_selected_mode"
    else:
        assert "real_world_efficacy" not in body["taiyi"]["ruleset"]
    if key == "sanshiunited" and view is None:
        assert body["synthesis"]["source_profiles"]["qimen"]
        profiles = body["qimen"]["rule_profiles"]
        for profile in ("god", "season", "wonder_tomb"):
            assert profiles[profile]["id"]
            assert profiles[profile]["variant_note"]
        assert profiles["wonder_tomb"]["source_priority_resolved"] is False
        assert profiles["wonder_tomb"]["whole_book_conformance_established"] is False
        assert body["liureng"]["ruleset"]
        assert body["liureng"]["three_transmissions"]
        assert (
            body["synthesis"]["time_scopes"]["taiyi"]
            == {
                "year": "year",
                "month": "solar_month",
                "day": "selected_clock_day",
                "hour": "double_hour",
            }[mode]
        )
    else:
        pass


@pytest.mark.parametrize(
    "key,payload,fields",
    [
        (
            "taiyi",
            {
                "analysis_year": 2026,
                "analysis_month": 2,
                "analysis_day": 4,
                "analysis_hour": 12,
                "analysis_timezone": "Asia/Shanghai",
                "use_true_solar_time": False,
            },
            ["taiyi"],
        ),
        (
            "sanshiunited",
            {
                "date": "2026-02-04",
                "time": "12:00:00",
                "timezone": "Asia/Shanghai",
                "use_true_solar_time": False,
            },
            ["taiyi", "synthesis"],
        ),
    ],
)
@pytest.mark.parametrize(
    "mode,hour_profile,month_profile",
    [
        ("year", None, None),
        ("month", None, None),
        ("month", None, "key_month_tianzheng_jie_v1"),
        ("day", None, None),
        ("hour", None, None),
        ("hour", "key_hour_winter_jiazi_v1", None),
    ],
)
def test_taiyi_evidence_across_real_transports(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key: str,
    payload,
    fields,
    mode: str,
    hour_profile: str | None,
    month_profile: str | None,
) -> None:
    payload = dict(payload)
    if key == "taiyi":
        payload.update(calculation_mode=mode, analysis_second=2)
        if month_profile:
            payload["month_profile"] = month_profile
        else:
            pass
        if hour_profile:
            payload["hour_profile"] = hour_profile
        else:
            pass
    else:
        payload.update(taiyi_options={"calculation_mode": mode}, time="12:00:02")
        if month_profile:
            payload["taiyi_options"]["month_profile"] = month_profile
        else:
            pass
        if hour_profile:
            payload["taiyi_options"]["hour_profile"] = hour_profile
        else:
            pass
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {
        "as_of": "2026-10-22T12:00:00+08:00",
        "detail": "audit",
        "fields": fields,
    }
    route = "/api/taiyi" if key == "taiyi" else "/api/divination/sanshi"
    response = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", options["as_of"]),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    target_name = "taiyi" if key == "taiyi" else "sanshi_combined_chart"

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client,
                SPECS[target_name].name,
                {**payload, **options},
                raise_on_error=False,
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    mcp = native.structured_content
    args = [SPECS[target_name].name]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    args += [
        "--as-of",
        options["as_of"],
        "--detail",
        "audit",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    status = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert status == 0, cli
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in (response.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    taiyi = bodies[0]["taiyi"]
    if mode == "year":
        assert taiyi["calendar_rules"]["year"] == 2025
    else:
        assert taiyi["calendar_rules"]["calculation_mode"] == mode
        assert "12:00:02" in taiyi["calendar_rules"]["civil_datetime"]
    assert taiyi["ruleset"]["classical_acceptance_passed"] is False
    assert "real_world_efficacy" not in taiyi["ruleset"]
    assert taiyi["core_board"]["main_count"] > 0


@pytest.mark.parametrize(
    "obsolete", [{"accNum": 0}, {"acc_num": 0}, {"rotation": "顺布"}]
)
def test_obsolete_options_rejected_by_rest_mcp_and_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], obsolete
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {
        "date": "2026-04-04",
        "time": "12:00:00",
        "use_true_solar_time": False,
        "taiyi_options": obsolete,
    }
    response = TestClient(api.app).post("/api/divination/sanshi", json=payload)
    assert response.status_code == 422

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client, "sanshi_combined_chart", payload, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert native.is_error
    capsys.readouterr()
    code = run(
        [
            "sanshi_combined_chart",
            "--date",
            payload["date"],
            "--time",
            payload["time"],
            "--use-true-solar-time",
            "false",
            "--taiyi-options",
            json.dumps(payload["taiyi_options"]),
        ]
    )
    assert code != 0
    result = json.loads(capsys.readouterr().out)
    option_name = next(iter(obsolete))
    for body in [response.json(), native.structured_content, result]:
        assert body["error_code"] == "validation_error"
        issue = body["issues"][0]
        assert issue["code"] == "extra_forbidden"
        assert option_name in issue["path"]
        assert "taiyi" not in body


@pytest.mark.parametrize("mode", ["year", "day"])
def test_hour_profile_is_rejected_in_non_hour_mode_on_all_transports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 4,
        "analysis_hour": 12,
        "use_true_solar_time": False,
        "calculation_mode": mode,
        "hour_profile": "key_hour_winter_jiazi_v1",
    }
    response = TestClient(api.app).post("/api/taiyi", json=payload)
    assert response.status_code == 422

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client, "taiyi", payload, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert native.is_error
    status = run(
        [
            "taiyi",
            "--analysis-year",
            "2026",
            "--analysis-month",
            "4",
            "--analysis-day",
            "4",
            "--analysis-hour",
            "12",
            "--use-true-solar-time",
            "false",
            "--calculation-mode",
            mode,
            "--hour-profile",
            "key_hour_winter_jiazi_v1",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert status != 0
    for result in [response.json(), native.structured_content, body]:
        assert result["error_code"] == "validation_error"
        assert "hour_profile" in result["issues"][0]["message"]
        assert "taiyi" not in result


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("view", ["daily_calendar", "daily_essences"])
def test_daily_first_views_preserve_unknowns_and_source_variants(
    key: str, view: str
) -> None:
    target_name = "taiyi" if key == "taiyi" else "sanshi_combined_chart"
    spec = next(s for s in CATALOG if s.name == target_name)
    inputs = example_input(spec)
    if key == "taiyi":
        inputs["calculation_mode"] = "day"
    else:
        inputs["taiyi_options"] = {"calculation_mode": "day"}

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(
                client,
                spec.name,
                {
                    **inputs,
                    "detail": "audit",
                    "fields": suggested_fields(spec, view=view),
                },
                raise_on_error=False,
            )
            return result

    result = asyncio.run(protocol())
    assert not result.is_error
    body = result.structured_content
    # A runtime-only delivery reference is allowed; business deferral is not.
    if view == "daily_essences":
        records = body["taiyi"]["ten_jing"]["records"]
        assert len(records) == 10
        assert records["heaven_time"]["palace"] in "子丑寅卯辰巳午未申酉戌亥"
        assert records["heaven_time"]["rule_evidence"]["unresolved"]
        assert records["taiyi_ordinal"]["palace"] is None
        assert records["taiyi_ordinal"]["ordinal"]
        assert body["taiyi"]["ten_jing"]["classical_acceptance_passed"] is False
    else:
        assert (
            body["taiyi"]["calendar_rules"]["day_origin"]["day_boundary"]
            == "00:00_selected_clock_modern_convention"
        )


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_daily_complete_board_audit_delivers_evidence_and_receipt(
    key: str,
) -> None:
    target_name = "taiyi" if key == "taiyi" else "sanshi_combined_chart"
    spec = next(s for s in CATALOG if s.name == target_name)
    inputs = example_input(spec)
    if key == "taiyi":
        inputs.update(calculation_mode="day", analysis_month=2, analysis_day=2)
    else:
        inputs.update(date="2026-02-02", taiyi_options={"calculation_mode": "day"})

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(
                client,
                spec.name,
                {
                    **inputs,
                    "detail": "audit",
                    "fields": ["taiyi"],
                },
            )
            assert "result_delivery" not in result.structured_content
            return result.structured_content

    body = asyncio.run(protocol())
    records = body["taiyi"]["ten_jing"]["records"]
    assert records["heaven_time"]["palace"] == "酉"
    assert {
        c["source_value"] for c in records["eight_winds"]["source_comparisons"]
    } == {"乾", "艮"}
    assert records["eight_winds"]["palace"] == "巽"
    assert body["taiyi"]["core_board"]["main_count"] == 33
    assert body["taiyi"]["day_source_comparisons"][0]["source_value"] == 32
