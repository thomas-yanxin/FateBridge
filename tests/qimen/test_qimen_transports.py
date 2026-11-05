"""The real REST, native MCP and CLI share Qimen evidence and errors."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app


@pytest.mark.parametrize(
    "method,date,hour,god_profile,season_profile",
    [
        ("zhirun", (2026, 1, 19), 23, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 19), 23, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 7, 5), 8, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 21), 0, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 15), 16, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 21), 5, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 21), 9, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 22), 2, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 23), 8, "yanyi_text", "yanyi_vol1_verse"),
        ("chaibu", (2026, 1, 21), 7, "yanyi_text", "yanyi_vol1_verse"),
        *[
            ("chaibu", (2026, 1, 19), 23, god, season)
            for god in ["yanyi_text", "yanyi_diagrams"]
            for season in ["yanyi_vol1_verse", "yanyi_vol3_table", "yanyi_vol3_prose"]
            if (god, season) != ("yanyi_text", "yanyi_vol1_verse")
        ],
    ],
)
def test_qimen_evidence_agrees_across_real_transports(
    monkeypatch, capsys, method, date, hour, god_profile, season_profile
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["four_pillars", "qimen", "snapshot_text", "snapshot_export"]
    year, month, day = date
    payload = dict(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={
            "ju_method": method,
            "god_profile": god_profile,
            "season_profile": season_profile,
        },
    )
    control = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/cn/qimen",
        json=payload,
        params=[
            ("as_of", control["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "qimen", {**payload, **control}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    assert native.structured_content == json.loads(native.content[0].text)
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            str(year),
            "--analysis-month",
            str(month),
            "--analysis-day",
            str(day),
            "--analysis-hour",
            str(hour),
            "--analysis-timezone",
            "Asia/Hong_Kong",
            "--no-use-true-solar-time",
            "--qimen-options",
            json.dumps(payload["qimen_options"]),
            "--as-of",
            control["as_of"],
            "--strict-fields",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    assert response.status_code == 200, response.text
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in [response.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    q = bodies[0]["qimen"]
    if month == 1 and day == 19:
        assert q["day_ganzhi"] == "甲午"
        assert q["time_ganzhi"] == "甲子"
        assert q["source_disagreements"] == []
    elif month == 1 and day == 15:
        assert q["stem_context"]["day"]["effective_stem"] == "己"
        assert any(p["rule_id"] == "flying_day_stem" for p in q["patterns"])
        d = q["source_disagreements"][0]
        assert d["case_id"] == "vol2-yang5-renshen-geng-palace"
        assert (d["source_value"], d["computed_value"]) == ("离", "坤")
        assert "heaven_geng_palace原文离，本盘坤" in bodies[0]["snapshot_text"]
    elif month == 1 and day == 22:
        assert q["time_ganzhi"] == "己丑"
        assert q["structure"]["hour_branch_tomb"]
        assert not q["stem_context"]["hour_branch_tomb"]["matched_definition"][
            "verse_listed"
        ]
        assert "己丑为正文补列" in bodies[0]["snapshot_text"]
    elif month == 1 and day == 23:
        assert q["time_ganzhi"] == "甲辰"
        assert q["stem_context"]["hour"]["effective_stem"] == "壬"
        assert q["structure"]["hour_branch_tomb"] is False
        assert not q["stem_context"]["hour_branch_tomb"][
            "heaven_stem_palace_tomb_evaluated"
        ]
    elif month == 1 and day == 21 and hour == 7:
        at = next(p for p in q["palaces"] if p["trigram"] == "乾")
        tomb = at["evidence"]["wonder_tomb"]
        assert tomb["selected_matched_stems"] == []
        assert tomb["unadopted_literal_candidate_matched_stems"] == ["乙"]
        assert not tomb["candidate_adopted"]
        assert not any(
            p["rule_id"] == "wonder_tomb" and p["palace"] == at["name"]
            for p in q["patterns"]
        )
        assert "王璋口径本宫命中无；段首字面候选命中乙" in bodies[0]["snapshot_text"]
    elif month == 1 and day == 21 and hour in {5, 9}:
        role, rule, stem, label = (
            ("year", "year_stem_block", "乙", "岁干")
            if hour == 5
            else ("lunar_month_start", "lunar_month_start_block", "癸", "月朔干")
        )
        pattern = next(p for p in q["patterns"] if p["rule_id"] == rule)
        assert pattern["facts"]["earth_stem"] == stem
        assert pattern["qualification"]["stem_identity"] == q["stem_context"][role]
        assert f"{label}取用" in bodies[0]["snapshot_text"]
        if hour == 9:
            assert pattern["facts"]["anchor_date"] == "2026-01-19"
            assert q["stem_context"][role]["ganzhi"] == "癸巳"
    elif month == 1:
        assert q["xun_head"] == "甲戌"
        pattern = next(
            p for p in q["patterns"] if p["rule_id"] == "dragon_returns_head"
        )
        assert pattern["facts"]["heaven_stem"] == "己"
        assert pattern["qualification"]["identity_binding"]["hidden_stem"] == "己"
        assert "时旬身份：甲戌遁己" in bodies[0]["snapshot_text"]
    else:
        assert q["time_ganzhi"] == "庚辰"
        d = q["source_disagreements"][0]
        assert d["case_id"] == "vol4-yin9-gengchen-door"
        assert (d["source_value"], d["computed_value"]) == ("坎", "坤")
        assert "raw_door_gong原文坎，本盘坤" in bodies[0]["snapshot_text"]
    assert q["ju_method"] == method
    assert q["god_profile"] == god_profile
    assert q["season_profile"] == season_profile
    assert q["rule_profiles"]["god"]["id"] == god_profile
    assert q["rule_profiles"]["season"]["id"] == season_profile
    assert not q["rule_profiles"]["wonder_tomb"]["source_priority_resolved"]
    assert all(
        not p["evidence"]["wonder_tomb"]["candidate_adopted"]
        for p in q["palaces"]
        if p["trigram"] != "中"
    )
    assert god_profile in bodies[0]["snapshot_text"]
    assert season_profile in bodies[0]["snapshot_text"]
    for palace in q["palaces"]:
        if palace["trigram"] != "中":
            assert palace["evidence"]["star_season_profile"] == season_profile
            assert palace["evidence"]["god_interpretation"]["god"] == palace["god"]
    assert q["assessment"]["authority_certified"] is False
    assert q["rule_trace"][0]["outputs"]["xun_head"] == q["xun_head"]
    assert bodies[0]["snapshot_export"]["export_text"] == bodies[0]["snapshot_text"]
    assert "换日：子初换日" in bodies[0]["snapshot_text"]
    assert "规则依据" in bodies[0]["snapshot_text"]


@pytest.mark.parametrize(
    "option,message",
    [
        ({"layout": "fly"}, "转盘"),
        *[
            ({key: value}, key)
            for key in ["god_profile", "season_profile"]
            for value in [None, {}, "automatic_best"]
        ],
    ],
)
def test_unsupported_qimen_options_fail_in_all_real_transports(
    monkeypatch, capsys, option, message
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=12,
        use_true_solar_time=False,
        qimen_options=option,
    )
    response = TestClient(api.app).post("/api/cn/qimen", json=payload)

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("qimen", payload, raise_on_error=False)

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            "2026",
            "--analysis-month",
            "1",
            "--analysis-day",
            "1",
            "--analysis-hour",
            "12",
            "--no-use-true-solar-time",
            "--qimen-options",
            json.dumps(option),
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert code != 0
    assert response.status_code in [400, 422]
    assert native.is_error
    for body in [response.json(), native.structured_content, cli]:
        assert "error" in body
        assert "qimen" not in body
        assert message in str(body)


def test_generated_qimen_contract_first_view_has_reading_evidence():
    from pathlib import Path

    from fatebridge.application.examples import example_input
    from fatebridge.services.tool_catalog import CATALOG

    record = json.loads(
        (Path(__file__).parents[2] / "docs/contracts/qimen.json").read_text()
    )
    fields = set(record["first_view"]["fields"])
    assert {
        "qimen.calendar_policy",
        "qimen.rulesets",
        "qimen.rule_profiles",
        "qimen.stem_context",
        "qimen.patterns",
        "qimen.palaces",
        "qimen.assessment",
        "qimen.source_disagreements",
    } <= fields
    spec = next(s for s in CATALOG if s.tool_name == "qimen")

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "qimen",
                {
                    **example_input(spec),
                    **record["first_view"],
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    result = asyncio.run(protocol())
    assert not result.is_error
    q = result.structured_content["qimen"]
    assert q["rulesets"] and q["calendar_policy"] and q["palaces"]
    assert q["assessment"]["real_world_efficacy"] == "not_tested"


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize(
    "month,day,hour,message",
    [(3, 8, 2, "nonexistent local time"), (11, 1, 1, "ambiguous local time")],
)
def test_invalid_civil_clocks_fail_in_all_real_transports(
    monkeypatch, capsys, solar, month, day, hour, message
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = dict(
        analysis_year=2026,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
        analysis_minute=30,
        analysis_timezone="America/New_York",
        analysis_longitude=-74.006,
        use_true_solar_time=solar,
    )
    response = TestClient(api.app).post("/api/cn/qimen", json=payload)

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("qimen", payload, raise_on_error=False)

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run(
        [
            "qimen",
            "--analysis-year",
            "2026",
            "--analysis-month",
            str(month),
            "--analysis-day",
            str(day),
            "--analysis-hour",
            str(hour),
            "--analysis-minute",
            "30",
            "--analysis-timezone",
            "America/New_York",
            "--analysis-longitude",
            "-74.006",
            "--use-true-solar-time" if solar else "--no-use-true-solar-time",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert code != 0
    assert response.status_code in [400, 422]
    assert native.is_error
    for body in [response.json(), native.structured_content, cli]:
        assert body["error_code"] == "validation_error"
        assert body["retryable"] is False
        assert message in body["error"]
        assert "qimen" not in body
