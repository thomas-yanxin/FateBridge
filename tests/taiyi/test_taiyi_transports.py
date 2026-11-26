"""Verify Taiyi transport consistency, §7 oracles, minute/fate/day modes, and gates."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.seed import build_analysis_seed
from fatebridge.core.metaphysics.taiyi import (
    build_taiyi_board,
    conjunction,
    yearly_core,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import SPECS, call_calculation


@pytest.mark.parametrize(
    "key,view",
    [
        ("taiyi", None),
        ("taiyi", "counter_cycles"),
        ("taiyi", "year_core"),
        ("taiyi", "annual_cycles"),
        ("taiyi", "conditions"),
        ("taiyi", "gates"),
        ("taiyi", "determinate"),
        ("sanshiunited", None),
        ("sanshiunited", "annual_cycles"),
        ("sanshiunited", "taiyi_conditions"),
        ("sanshiunited", "taiyi_gates"),
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
def test_published_first_views_preserve_evidence_and_adjudications(
    key: str,
    view: str | None,
    mode: str,
    hour_profile: str | None,
    month_profile: str | None,
) -> None:
    target_name = "taiyi" if key == "taiyi" else "sanshi_combined_chart"
    spec = next(s for s in CATALOG if s.name == target_name)
    inputs = example_input(spec)
    assert inputs is not None
    if key == "taiyi":
        inputs["calculation_mode"] = mode
        if month_profile:
            inputs["month_profile"] = month_profile
        if hour_profile:
            inputs["hour_profile"] = hour_profile
    else:
        inputs["taiyi_options"] = {"calculation_mode": mode}
        if month_profile:
            inputs["taiyi_options"]["month_profile"] = month_profile
        if hour_profile:
            inputs["taiyi_options"]["hour_profile"] = hour_profile

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client,
                spec.name,
                {
                    **inputs,
                    "detail": "audit",
                    "fields": suggested_fields(spec, view=view),
                },
                raise_on_error=False,
            )

    result = asyncio.run(protocol())
    assert not result.is_error, result
    body = result.structured_content
    if view in {"conditions", "taiyi_conditions"}:
        assessment = body["taiyi"]["condition_assessment"]
        assert len(assessment["five_generals"]["clauses"]) == 3
        assert assessment["three_gates"]["status"] == "computed"
        assert type(assessment["three_gates"]["conditions_satisfied"]) is bool
        assert type(assessment["menju_jiangfa"]) is bool
        assert assessment["menju_jiangfa"] is conjunction(
            assessment["five_generals"]["conditions_satisfied"],
            assessment["three_gates"]["conditions_satisfied"],
        )
        assert body["taiyi"]["ruleset"]["classical_conformance"] == "implemented"
        assert body["taiyi"]["ruleset"]["classical_acceptance_passed"] is True
    elif view in {"gates", "taiyi_gates"}:
        gates = body["taiyi"]["gates"]
        assert gates["status"] == "computed"
        assert gates["selected_profile"]
        assert gates["ruleset"]["classical_acceptance_passed"] is True
    elif view in {"determinate", "taiyi_determinate"}:
        det = body["taiyi"]["determinate_calculation"]
        assert det["status"] == "computed"
    elif view == "annual_cycles":
        cycles = body["taiyi"]["long_cycles"]
        assert cycles["time_granularity"] == "year"
        if mode == "year":
            assert len(cycles["records"]) == 11
            assert cycles["ruleset"]["classical_acceptance_passed"] is True
        else:
            assert cycles["status"] == "not_computed_for_selected_mode"
    if key == "sanshiunited" and view is None:
        assert body["liureng"]["ruleset"]
        assert body["liureng"]["three_transmissions"]


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
        if hour_profile:
            payload["hour_profile"] = hour_profile
    else:
        payload.update(taiyi_options={"calculation_mode": mode}, time="12:00:02")
        if month_profile:
            payload["taiyi_options"]["month_profile"] = month_profile
        if hour_profile:
            payload["taiyi_options"]["hour_profile"] = hour_profile

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
        params=[("as_of", options["as_of"]), ("detail", "audit")]
        + [("fields", f) for f in fields],
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
    args += ["--as-of", options["as_of"], "--detail", "audit", "--fields", *fields]
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
    assert taiyi["ruleset"]["classical_acceptance_passed"] is True
    assert taiyi["core_board"]["main_count"] > 0


def test_taiyi_classical_year_oracles() -> None:
    # 724 CE Kaiyuan 12 = 1937281 -> Yang 49: Taiyi=1(乾), Wenchang=巽, Shiji=辰, main=24, guest=25, suijun=子, heshen=丑
    c724 = yearly_core(724)
    assert c724["accumulation"] == 1937281
    assert c724["kook_number"] == 49
    assert c724["taiyi_number"] == 1
    assert c724["taiyi_palace"] == "乾"
    assert c724["wenchang_palace"] == "巽"
    assert c724["shiji"] == "辰"
    assert c724["main_count"] == 24
    assert c724["guest_count"] == 25
    assert c724["suijun"] == "子"
    assert c724["heshen"] == "丑"

    # 2024 CE Jiachen = 1938581 -> Yang 53: Taiyi=2(午), Wenchang=坤, Shiji=亥, main=38, guest=25
    c2024 = yearly_core(2024)
    assert c2024["accumulation"] == 1938581
    assert c2024["kook_number"] == 53
    assert c2024["taiyi_number"] == 2
    assert c2024["taiyi_palace"] == "午"
    assert c2024["wenchang_palace"] == "坤"
    assert c2024["shiji"] == "亥"
    assert c2024["main_count"] == 38
    assert c2024["guest_count"] == 25


def test_taiyi_day_minute_and_fate_modes() -> None:
    seed = build_analysis_seed(
        analysis_year=2024,
        analysis_month=5,
        analysis_day=20,
        analysis_hour=14,
        analysis_minute=30,
        analysis_second=0,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    # Default jinjing_day_v1
    day_jj = build_taiyi_board(seed, "男", calculation_mode="day")
    assert day_jj["calendar_rules"]["day_profile"] == "jinjing_day_v1"
    assert day_jj["gates"]["status"] == "computed"
    assert type(day_jj["condition_assessment"]["menju_jiangfa"]) is bool
    assert len(json.dumps(day_jj, ensure_ascii=False)) < 25000

    # Key day profile
    day_key = build_taiyi_board(
        seed, "男", calculation_mode="day", day_profile="key_day_winter_jiazi_v1"
    )
    assert day_key["calendar_rules"]["day_profile"] == "key_day_winter_jiazi_v1"
    assert day_key["ten_jing"]["classical_acceptance_passed"] is True
    assert len(day_key["ten_jing"]["records"]) == 9

    # Minute (刻家太乙)
    minute_b = build_taiyi_board(seed, "男", calculation_mode="minute")
    assert minute_b["calendar_rules"]["calculation_mode"] == "minute"
    assert minute_b["counter_cycles"]["counter_unit"] == "刻"
    assert minute_b["gates"]["status"] == "computed"
    assert type(minute_b["condition_assessment"]["menju_jiangfa"]) is bool

    # Fate (太乙命法)
    fate_b = build_taiyi_board(seed, "男", calculation_mode="fate")
    assert fate_b["calendar_rules"]["calculation_mode"] == "fate"
    assert fate_b["interpretation_scope"]["gender_used"] is True
    assert len(fate_b["fate_palaces"]["twelve_palaces"]) == 12
    assert fate_b["fate_palaces"]["twelve_palaces"][0]["palace"] == "命宫"
    assert fate_b["fate_palaces"]["life_palace"] in "子丑寅卯辰巳午未申酉戌亥"
    assert fate_b["fate_palaces"]["body_palace"] in "子丑寅卯辰巳午未申酉戌亥"
