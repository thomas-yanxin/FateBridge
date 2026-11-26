"""Scope identity and natal-star joins across REST, MCP, and CLI."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from tests.support.transports import call_calculation

TARGET = dict(analysis_year=2027, analysis_month=6, analysis_day=15, analysis_hour=12)
BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    gender="男",
    birth_place="北京",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=True,
)
FIELDS = ["analysis_context", "birth_context", "ziwei_horoscope"]


def _calculate(birth=BIRTH, target=TARGET):
    return calculate_ziwei_horoscope(create_person_info(**birth), **target)


def test_target_receipt_is_not_the_birth_receipt() -> None:
    result = _calculate()
    target, birth = result["analysis_context"], result["birth_context"]
    assert target["context_role"] == "target" and birth["context_role"] == "birth"
    assert target["analysis_datetime"] == "2027-06-15 12:00:00"
    assert target["input_datetime"] == target["corrected_datetime"]
    assert [
        target[f"analysis_{part}"]
        for part in ("year", "month", "day", "hour", "minute")
    ] == [2027, 6, 15, 12, 0]
    assert target["time_algorithm"] == "直接时间"
    assert birth["input_datetime"] == "1992-08-15 14:30:00"


def test_target_timezone_does_not_inherit_birth_timezone() -> None:
    result = _calculate(
        {**BIRTH, "birth_timezone": "America/New_York", "use_true_solar_time": False}
    )
    assert result["birth_context"]["timezone"] == "America/New_York"
    assert result["analysis_context"]["timezone"] == "Asia/Shanghai"
    assert result["analysis_context"]["analysis_hour"] == 12


@pytest.mark.parametrize(
    "birth",
    [
        BIRTH,
        dict(
            birth_year=1989,
            birth_month=5,
            birth_day=23,
            birth_hour=8,
            birth_minute=40,
            gender="女",
            birth_place="成都",
        ),
        dict(
            birth_year=1986,
            birth_month=1,
            birth_day=30,
            birth_hour=23,
            birth_minute=50,
            gender="男",
            birth_place="上海",
        ),
    ],
)
def test_scope_transformations_join_to_actual_natal_star_data(birth) -> None:
    result = _calculate(birth)
    natal = calculate_ziwei_birth(create_person_info(**birth))["ziwei_birth"]
    horoscope = result["ziwei_horoscope"]
    assert not horoscope["interpretation_scope"]["full_scope_palaces_supported"]
    for scope in horoscope["scopes"]:
        assert scope["scope_palace_role"] == "ming_palace_activity_index"
        palace = next(
            p for p in natal["palaces"] if p["ganzhi"] == scope["palace_ganzhi"]
        )
        assert scope["natal_palace_name"] == palace["name"]
        assert len(scope["mutagen_natal_links"]) == 4
        for link in scope["mutagen_natal_links"]:
            assert scope["mutagen"][link["transformation"]] == link["star"]
            p = next(
                p for p in natal["palaces"] if p["name"] == link["natal_palace_name"]
            )
            star = next(s for s in p["stars_detail"] if s["name"] == link["star"])
            assert link["natal_branch"] == p["ganzhi"][1]
            if star["brightness"] is not None:
                assert link["natal_star_brightness"] == star["brightness"]
            if star["mutagen"] is not None:
                assert link["natal_mutagen"] == star["mutagen"]


def test_annual_transformation_in_natal_career_is_not_annual_career_palace() -> None:
    annual = next(
        s for s in _calculate()["ziwei_horoscope"]["scopes"] if s["scope"] == "流年"
    )
    assert annual["natal_palace_name"] == "迁移宫"
    career = next(
        link for link in annual["mutagen_natal_links"] if link["star"] == "天机"
    )
    assert career["transformation"] == "化科"
    assert career["natal_palace_name"] == "官禄宫"
    assert career["natal_branch"] == "巳"


def test_late_zi_natal_day_keeps_current_day_with_explicit_solar_convention() -> None:
    person = create_person_info(
        birth_year=1986,
        birth_month=1,
        birth_day=30,
        birth_hour=23,
        birth_minute=50,
        birth_place="上海",
        gender="男",
        use_true_solar_time=True,
    )
    natal = calculate_ziwei_birth(person)["ziwei_birth"]
    assert natal["lunar_date"] == dict(year=1985, month=12, day=21, is_leap_month=False)
    assert natal["ming_gong"]["ganzhi"] == "己丑"
    result = calculate_ziwei_horoscope(person, **TARGET)
    assert result["birth_context"]["lunar_display"] == "腊月廿一"
    assert result["ziwei_horoscope"]["nominal_age"] == 43


def test_context_scope_and_natal_linkage_match_rest_mcp_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = {**BIRTH, **TARGET}
    options = dict(
        as_of="2026-10-20T00:45:00+08:00",
        detail="audit",
        fields=FIELDS,
    )
    response = TestClient(api.app).post(
        "/api/ziwei/timing",
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("detail", "audit"),
            *[("fields", field) for field in FIELDS],
        ],
    )

    async def mcp_call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await call_calculation(
                client, "ziwei_timing", {**inputs, **options}, raise_on_error=False
            )

    protocol = asyncio.run(mcp_call())
    assert response.status_code == 200, response.json()
    assert not protocol.is_error, protocol.content
    args = ["ziwei_timing"]
    for key, value in inputs.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.extend(
        [
            "--as-of",
            options["as_of"],
            "--detail",
            "audit",
            "--fields",
            *FIELDS,
        ]
    )
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    payloads = [response.json(), protocol.structured_content, cli]
    for field in FIELDS:
        assert payloads[0][field] == payloads[1][field] == payloads[2][field]
    assert payloads[0]["analysis_context"]["analysis_datetime"] == "2027-06-15 12:00:00"
    assert payloads[0]["birth_context"]["input_datetime"] == "1992-08-15 14:30:00"
