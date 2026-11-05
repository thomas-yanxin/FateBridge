"""Source month origin, lunar/Jie mismatch, all gate conflicts and transports."""

import asyncio
import hashlib
import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_month import KEY_MONTH_PROFILE, key_month_origin
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.core.output_chinese import Taiyi
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.taiyi.audit_taiyi_gate_sectors import audit as sector_audit
from scripts.taiyi.audit_taiyi_month import CORPUS, audit, public_case
from tests.taiyi.test_taiyi_periods import seed_at
from tests.taiyi.test_taiyi_transports import _same_run_payload


def test_all_month_requirements_keep_arithmetic_disagreements_and_incomplete_chart_label():
    report = audit()
    assert (
        report["required_observations"],
        report["evaluated_observations"],
        report["matching_observations"],
    ) == (29, 28, 23)
    assert {r["id"] for r in report["disagreements"]} == {
        "gate_accumulation",
        "gate_remainder",
        "duty_gate",
        "unit_in_gate",
        "months_remaining",
    }
    assert [r["id"] for r in report["unadjudicated"]] == ["chart_ju"]
    assert report["selected_calendar_facts_passed"] is True
    assert report["source_example_acceptance_passed"] is False
    assert report["source_gate_arithmetic_diagnostic"]["computed_remainder"] == 204
    assert report["source_gate_arithmetic_diagnostic"]["printed_remainder"] == 184
    assert report["source_gate_arithmetic_diagnostic"]["equal"] is False
    assert report["full_ancient_calendar_reconstructed"] is False


def test_all_sixteen_gate_sectors_include_both_branches_of_each_corner():
    from fatebridge.core.metaphysics.taiyi_gates import (
        SECTORS,
        check_three_gates,
        gate_frame,
    )

    report = sector_audit()
    assert report["required_observations"] == report["matching_observations"] == 16
    assert report["geometry_acceptance_passed"] is True
    assert {s: SECTORS[s] for s in "丑辰未戌"} == {"丑": 3, "辰": 9, "未": 7, "戌": 1}
    frame = gate_frame(1, "开", "test.taiyi")
    check = check_three_gates(
        frame,
        [{"label": "文昌", "position": "戌", "source_path": "taiyi.wenchang_palace"}],
        "test.frame",
    )
    assert check["checks"][0]["door"] == "开"
    assert check["conditions_satisfied"] is False


@pytest.mark.parametrize(
    "year,door,satisfied", [(1911, "开", False), (2019, "伤", True)]
)
def test_public_year_gate_judgment_uses_source_chen_xunsi_sector_in_both_directions(
    year, door, satisfied
):
    result = calculate_taiyi_analysis(
        analysis_year=year,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="+08:00",
    )
    b = result["taiyi"]
    check = b["condition_assessment"]["three_gates"]
    eye = check["checks"][1]
    assert (eye["position"], eye["sector_number"], eye["door"]) == ("辰", 9, door)
    assert check["conditions_satisfied"] is satisfied
    assert b["condition_assessment"]["menju_jiangfa"] is False


@pytest.mark.parametrize("year", [1, 724, 1504, 1561, 2026, 9998])
def test_full_positive_months_align_with_shortcut_on_all_shared_cycles(year):
    for offset in range(12):
        origin = key_month_origin(year, offset)
        assert origin["accumulation"] > 0
        assert origin["full_minus_shortcut"] == 121865040
        assert origin["all_shared_cycles_aligned"] is True
        for period in (12, 18, 24, 72, 240, 360, 720):
            assert origin["accumulation"] % period == origin["shortcut_count"] % period
        if origin["shortcut_count"] > 0:
            full = cyclic_core(origin["accumulation"])
            short = cyclic_core(origin["shortcut_count"])
            assert {k: v for k, v in full.items() if k != "accumulation"} == {
                k: v for k, v in short.items() if k != "accumulation"
            }


def test_source_example_is_real_public_chain_and_gate_input_cannot_be_chosen_to_fit():
    r = public_case()
    b = r["taiyi"]
    assert b["core_board"]["accumulation"] == 121865735
    assert b["core_board"]["kook_number"] == 47
    assert (
        b["core_board"]["main_count"],
        b["core_board"]["guest_count"],
        b["core_board"]["set_count"],
    ) == (4, 8, 17)
    assert (
        b["gates"]["counter"]["duty_gate"] == "惊"
        and b["gates"]["counter"]["unit_in_gate"] == 5
    )
    assert b["gates"]["moving_frame"]["anchor_palace"] == "乾"
    assert b["gates"]["moving_frame"]["anchor_source_value"] == "戌"
    assert b["condition_assessment"]["three_gates"]["status"] == "not_assessed"
    assert b["condition_assessment"]["five_generals"]["conditions_satisfied"] is False
    assert b["condition_assessment"]["three_gates"]["conditions_satisfied"] is None
    assert b["condition_assessment"]["menju_jiangfa"] is False
    assert [
        (v["accumulation"], v["cycle_position"], v["duty_gate"], v["unit_in_gate"])
        for v in b["gates"]["source_counter_alternatives"]
    ] == [(684, 204, "死", 24), (184, 184, "死", 4)]
    assert len(b["gates"]["source_comparisons"]) == 5
    assert "原文死，本盘规则推算惊" in r["snapshot_text"]
    assert "不是本盘所用积月" in r["snapshot_text"]
    assert b["ruleset"]["classical_acceptance_passed"] is False
    Taiyi.model_validate(b)


def test_lunar_month_and_selected_jie_month_are_not_conflated():
    yes = public_case()["taiyi"]["calendar_rules"]["month_origin"]["calendar_reference"]
    no = public_case(day=10, month=11)["taiyi"]["calendar_rules"]["month_origin"][
        "calendar_reference"
    ]
    assert yes["month_label_matches"] is yes["counter_matches"] is True
    assert (no["source_month"], no["actual_nominal_month"]) == (9, 10)
    assert no["month_label_matches"] is no["counter_matches"] is False
    assert no["next_lunar_month_start_gregorian"] == "1561-11-17"


@pytest.mark.parametrize("name", ["大雪", "小寒", "立春", "立冬"])
def test_jie_boundary_adds_one_without_resetting_at_civil_or_nominal_year(name):
    t = next(t for t in get_solar_terms_for_year(2026, "UTC") if t.name == name)
    boards = []
    for delta in (-1, 1):
        moment = (t.moment + timedelta(microseconds=delta)).replace(tzinfo=None)
        seed = replace(seed_at(moment, zone="UTC"), input_datetime=moment)
        boards.append(
            build_taiyi_board(
                seed, "未知", calculation_mode="month", month_profile=KEY_MONTH_PROFILE
            )
        )
    assert (
        boards[1]["core_board"]["accumulation"]
        - boards[0]["core_board"]["accumulation"]
        == 1
    )
    assert (
        boards[0]["calendar_rules"]["counter"]
        == boards[0]["calendar_rules"]["month_origin"]["accumulation"]
    )


def test_default_jinjing_corrects_nominal_year_without_switching_profile():
    kwargs = dict(
        analysis_year=1561,
        analysis_month=10,
        analysis_day=20,
        analysis_hour=12,
        analysis_timezone="+08:00",
        calculation_mode="month",
    )
    default = calculate_taiyi_analysis(**kwargs)
    explicit = calculate_taiyi_analysis(
        **kwargs, month_profile="jinjing_month_jie_360_v1"
    )
    assert default == explicit
    assert default["taiyi"]["ruleset"]["id"] == "jinjing_month_jie_360_v1"
    assert default["taiyi"]["core_board"]["kook_number"] == 47
    assert default["taiyi"]["ruleset"]["version"] == "1.2.0"
    assert public_case()["taiyi"]["core_board"]["kook_number"] == 47


@pytest.mark.parametrize(
    "mode,profile",
    [
        ("year", KEY_MONTH_PROFILE),
        ("day", KEY_MONTH_PROFILE),
        ("hour", KEY_MONTH_PROFILE),
        ("month", "invented"),
        ("month", False),
    ],
)
def test_month_profile_validation_prevents_cross_mode_or_unpublished_methods(
    mode, profile
):
    with pytest.raises(ValueError, match="month_profile"):
        build_taiyi_board(
            seed_at(datetime(2026, 4, 4, 12)),
            "未知",
            calculation_mode=mode,
            month_profile=profile,
        )


def test_each_new_month_fact_can_be_strictly_projected_and_typed():
    b = public_case()["taiyi"]

    def leaves(obj, path):
        if isinstance(obj, dict) and obj:
            for key, value in obj.items():
                yield from leaves(value, (*path, key))
        else:
            yield ".".join(path)

    for field in list(
        leaves(
            b["calendar_rules"]["month_origin"],
            ("taiyi", "calendar_rules", "month_origin"),
        )
    ) + ["taiyi.gates.source_comparisons", "taiyi.gates.source_counter_alternatives"]:
        Taiyi.model_validate(
            project_fields({"taiyi": b}, [field], strict_fields=True)["taiyi"]
        )


@pytest.mark.parametrize("mode", ["year", "day", "hour"])
def test_month_profile_wrong_mode_is_rejected_on_all_actual_transports(
    monkeypatch, capsys, mode
):
    payload = {
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 4,
        "analysis_hour": 12,
        "calculation_mode": mode,
        "month_profile": KEY_MONTH_PROFILE,
        "use_true_solar_time": False,
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post("/api/cn/taiyi", json=payload)
    assert rest.status_code == 400

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool("taiyi", payload, raise_on_error=False)

    mcp = asyncio.run(invoke())
    assert mcp.is_error
    capsys.readouterr()
    code = run(
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
            "--calculation-mode",
            mode,
            "--month-profile",
            KEY_MONTH_PROFILE,
            "--no-use-true-solar-time",
        ]
    )
    assert code != 0
    cli = json.loads(capsys.readouterr().out)
    for body in (rest.json(), mcp.structured_content, cli):
        assert "month_profile" in body["error"] and "taiyi" not in body


@pytest.mark.parametrize("target", ["gate_remainder", "chart_ju"])
def test_oracle_cannot_drop_failed_or_unknown_requirement_even_after_rehash(
    tmp_path, target
):
    base = tmp_path / "fixtures"
    for p in CORPUS.parent.glob("taiyi_jinjing_v*"):
        shutil.copytree(p, base / p.name)
    c = base / CORPUS.name
    p = c / "month-worked.json"
    d = json.loads(p.read_text())
    d["observations"] = [r for r in d["observations"] if r["id"] != target]
    p.write_text(json.dumps(d))
    m = json.loads((c / "manifest.json").read_text())
    for row in m["source_files"]:
        if row["file"] == p.name:
            row["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    m["source_reference"]["file"] = str(
        (CORPUS / m["source_reference"]["file"]).resolve()
    )
    m["observation_count"] = 28
    (c / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="29要求"):
        audit(c)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_month_first_view_keeps_source_conflicts_and_restores_same_run(key):
    s = next(s for s in CATALOG if s.key == key)
    payload = (
        {
            "analysis_year": 1561,
            "analysis_month": 10,
            "analysis_day": 20,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "calculation_mode": "month",
            "month_profile": KEY_MONTH_PROFILE,
        }
        if key == "taiyi"
        else {
            "date": "1561-10-20",
            "time": "12:00:00",
            "zone": "+08:00",
            "taiyi_options": {
                "calculation_mode": "month",
                "month_profile": KEY_MONTH_PROFILE,
            },
        }
    )

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                key,
                {
                    **payload,
                    "use_true_solar_time": False,
                    "fields": suggested_fields(s, view="monthly_key_calendar"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
                raise_on_error=False,
            )
            await _same_run_payload(client, result, require_business_inline=True)
            return result.structured_content

    body = asyncio.run(invoke())
    assert len(body["taiyi"]["gates"]["source_comparisons"]) == 5


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("month,day,matched", [(10, 20, True), (11, 10, False)])
def test_month_source_facts_across_actual_rest_native_mcp_and_cli(
    monkeypatch, capsys, key, month, day, matched
):
    payload = (
        {
            "analysis_year": 1561,
            "analysis_month": month,
            "analysis_day": day,
            "analysis_hour": 12,
            "analysis_timezone": "+08:00",
            "calculation_mode": "month",
            "month_profile": KEY_MONTH_PROFILE,
        }
        if key == "taiyi"
        else {
            "date": f"1561-{month:02d}-{day:02d}",
            "time": "12:00:00",
            "zone": "+08:00",
            "taiyi_options": {
                "calculation_mode": "month",
                "month_profile": KEY_MONTH_PROFILE,
            },
        }
    )
    payload["use_true_solar_time"] = False
    s = next(s for s in CATALOG if s.key == key)
    fields = suggested_fields(s, view="monthly_key_calendar")
    opts = {
        "fields": fields,
        "strict_fields": True,
        "response_char_limit": 0,
        "as_of": "2026-10-22T12:00:00+08:00",
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    route = "/api/cn/taiyi" if key == "taiyi" else "/api/divination/sanshiunited"
    rest = TestClient(api.app).post(
        route,
        json=payload,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            v = await client.call_tool(key, {**payload, **opts}, raise_on_error=False)
            assert not v.is_error, v
            return v.structured_content

    mcp = asyncio.run(invoke())
    argv = [key]
    for name, value in payload.items():
        argv += [
            "--" + name.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    argv += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in (rest.json(), mcp, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert (
        bodies[0]["taiyi"]["calendar_rules"]["month_origin"]["calendar_reference"][
            "month_label_matches"
        ]
        is matched
    )
