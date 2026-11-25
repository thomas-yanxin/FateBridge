"""Scope identity and natal-star joins must survive every public transport."""

import asyncio
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    rest,
    surface_calls,
    three_surfaces,
)

TARGET = dict(target_year=2027, target_month=6, target_day=15, target_hour=12)
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


def test_target_receipt_is_not_the_birth_receipt():
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


def test_target_timezone_does_not_inherit_birth_timezone():
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
def test_scope_transformations_join_to_actual_natal_star_data(birth):
    result = _calculate(birth)
    natal = calculate_ziwei_birth(create_person_info(**birth))["ziwei_birth"]
    horoscope = result["ziwei_horoscope"]
    assert not horoscope["interpretation_scope"]["full_scope_palaces_supported"]
    for scope in horoscope["scopes"]:
        assert scope["scope_palace_role"] == "ming_palace_activity_index"
        palace = next(
            p for p in natal["palaces"] if p["ganzhi"] == scope["palace_ganzhi"]
        )
        assert scope["natal_palace_name"] == scope["palace_name"] == palace["name"]
        assert len(scope["mutagen_natal_links"]) == 4
        for link in scope["mutagen_natal_links"]:
            assert link["status"] == "matched"
            assert scope["mutagen"][link["transformation"]] == link["star"]
            p = next(
                p for p in natal["palaces"] if p["name"] == link["natal_palace_name"]
            )
            star = next(s for s in p["stars_detail"] if s["name"] == link["star"])
            assert link["natal_palace_ganzhi"] == p["ganzhi"]
            assert link["natal_branch"] == p["ganzhi"][1]
            assert link["natal_star_label"] == star["label"]
            assert link["natal_star_brightness"] == star["brightness"]
            assert link["natal_mutagen"] == star["mutagen"]


def test_annual_transformation_in_natal_career_is_not_annual_career_palace():
    annual = next(
        s for s in _calculate()["ziwei_horoscope"]["scopes"] if s["scope"] == "流年"
    )
    assert annual["natal_palace_name"] == "迁移宫"
    career = next(
        link for link in annual["mutagen_natal_links"] if link["star"] == "天机"
    )
    assert career["transformation"] == "化科"
    assert career["natal_palace_name"] == "官禄宫"
    assert career["natal_palace_ganzhi"] == "乙巳"


def test_late_zi_natal_day_keeps_current_day_with_explicit_solar_convention():
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


@pytest.mark.parametrize("day_divide", ["current", "forward"])
@pytest.mark.parametrize(
    "calendar_date",
    [date(2026, 10, 9), date(2024, 2, 9), date(2023, 3, 21), date(2033, 12, 21)],
)
def test_late_zi_uses_one_selected_date_for_natal_and_flowing_scopes(
    calendar_date, day_divide
):
    """Late Zi previously mixed today's lunar placement with tomorrow's stems."""
    selected_date = calendar_date + timedelta(days=day_divide == "forward")
    birth = {
        **BIRTH,
        "birth_year": calendar_date.year,
        "birth_month": calendar_date.month,
        "birth_day": calendar_date.day,
        "birth_hour": 23,
        "birth_minute": 30,
        "use_true_solar_time": False,
    }
    midnight_birth = {
        **birth,
        "birth_year": selected_date.year,
        "birth_month": selected_date.month,
        "birth_day": selected_date.day,
        "birth_hour": 0,
        "birth_minute": 0,
    }
    actual_result = calculate_ziwei_birth(
        create_person_info(**birth), day_divide=day_divide
    )
    actual = actual_result["ziwei_birth"]
    placement = actual["lunar_date"]
    assert (
        f"{placement['year']}年{placement['month']}月{placement['day']}日"
        in actual_result["snapshot_text"]
    )
    expected = calculate_ziwei_birth(create_person_info(**midnight_birth))[
        "ziwei_birth"
    ]
    for field in ("lunar_date", "ming_gong", "shen_gong", "palaces", "sihua"):
        assert actual[field] == expected[field]
    person = create_person_info(**{**BIRTH, "use_true_solar_time": False})
    target = dict(
        target_year=calendar_date.year,
        target_month=calendar_date.month,
        target_day=calendar_date.day,
        target_hour=23,
        target_minute=30,
    )
    actual_flow = calculate_ziwei_horoscope(person, **target, day_divide=day_divide)[
        "ziwei_horoscope"
    ]
    expected_flow = calculate_ziwei_horoscope(
        person,
        target_year=selected_date.year,
        target_month=selected_date.month,
        target_day=selected_date.day,
        target_hour=0,
    )["ziwei_horoscope"]
    for actual_scope, expected_scope in zip(
        actual_flow["scopes"][2:], expected_flow["scopes"][2:]
    ):
        for field in ("branch", "stem", "mutagen", "palace_map", "mutagen_natal_links"):
            assert actual_scope[field] == expected_scope[field]
    assert actual_flow["ruleset"]["day_divide"] == day_divide
    if calendar_date == date(2024, 2, 9) and day_divide == "forward":
        assert actual_flow["nominal_age"] + 1 == expected_flow["nominal_age"]
        assert actual_flow["scopes"][2]["stem"] == "甲"
    else:
        assert actual_flow["nominal_age"] == expected_flow["nominal_age"]


@pytest.mark.parametrize("day_divide", ["current", "forward"])
@pytest.mark.parametrize("target_hour", [23, 0])
def test_late_zi_selection_survives_strict_public_projection(
    day_divide, target_hour, tmp_path, monkeypatch, capsys
):
    payload = {
        **BIRTH,
        "use_true_solar_time": False,
        "day_divide": day_divide,
        "target_year": 2024,
        "target_month": 2,
        "target_day": 9 if target_hour == 23 else 10,
        "target_hour": target_hour,
        "target_minute": 30,
    }
    result = three_surfaces(
        SPECS["ziwei_horoscope"],
        payload,
        [
            "ziwei_horoscope.scopes",
            "ziwei_horoscope.ruleset.day_divide",
            "ziwei_horoscope.calendar_rules",
            "ziwei_horoscope.nominal_age_calendar",
            "ziwei_horoscope.calendar_basis.target",
        ],
        AS_OF,
        tmp_path,
        monkeypatch,
        capsys,
    )["ziwei_horoscope"]
    assert result["ruleset"]["day_divide"] == day_divide
    assert result["nominal_age_calendar"]["target_civil_lunar_year"] == (
        2023 if target_hour == 23 else 2024
    )
    assert result["calendar_rules"]["day_divide"] == day_divide
    basis = result["calendar_basis"]["target"]
    selected_new_year = day_divide == "forward" or target_hour == 0
    assert basis["placement_lunar_date"] == dict(
        year=2024 if selected_new_year else 2023,
        month=1 if selected_new_year else 12,
        day=1 if selected_new_year else 30,
        is_leap_month=False,
    )
    assert all(scope["stem_origin"] for scope in result["scopes"])
    assert len(result["scopes"][2]["flowing_stars"]) == 3
    daily = result["scopes"][4]
    hourly = result["scopes"][5]
    assert daily["stem"] == (
        "甲" if day_divide == "forward" or target_hour == 0 else "癸"
    )
    assert hourly["stem"] == ("甲" if daily["stem"] == "甲" else "壬")


@pytest.mark.parametrize("day_divide", ["current", "forward"])
@pytest.mark.parametrize("tool", ["ziwei_birth", "ziwei_rules"])
def test_late_zi_natal_and_rules_publish_selection(
    day_divide, tool, tmp_path, monkeypatch, capsys
):
    birth = {
        **BIRTH,
        "birth_year": 2024,
        "birth_month": 2,
        "birth_day": 9,
        "birth_hour": 23,
        "birth_minute": 30,
        "use_true_solar_time": False,
    }
    payload = {"day_divide": day_divide}
    if tool == "ziwei_birth":
        payload.update(birth)
        fields = [
            "ziwei_birth.lunar_date",
            "ziwei_birth.ruleset.day_divide",
            "ziwei_birth.calendar_basis",
        ]
    else:
        fields = ["rule_catalogue.ruleset.day_divide"]
    result = three_surfaces(
        SPECS[tool], payload, fields, AS_OF, tmp_path, monkeypatch, capsys
    )
    if tool == "ziwei_birth":
        natal = result["ziwei_birth"]
        basis = natal["calendar_basis"]
        assert basis["placement_lunar_date"] == natal["lunar_date"]
        assert basis["civil_date_lunar_date"] == dict(
            year=2023, month=12, day=30, is_leap_month=False
        )
        assert basis["date_shift_days"] == (day_divide == "forward")
        assert basis["day_boundary"].startswith(
            "23:00" if day_divide == "forward" else "00:00"
        )
        assert natal["ruleset"]["day_divide"] == day_divide
    else:
        assert result["rule_catalogue"]["ruleset"]["day_divide"] == day_divide


def test_forward_late_zi_full_response_matches_all_transports(surface_calls):
    """Selected dates must agree in complete receipts as well as strict projections."""
    payload = {
        **BIRTH,
        "use_true_solar_time": False,
        "day_divide": "forward",
        "target_year": 2024,
        "target_month": 2,
        "target_day": 9,
        "target_hour": 23,
        "target_minute": 30,
    }
    options = {"response_char_limit": 0, "include_snapshot_text": False}
    response, protocol, code, local = surface_calls(
        SPECS["ziwei_horoscope"],
        payload,
        params={"as_of": AS_OF, **options},
        options=options,
        flags=["--response-char-limit", "0", "--no-include-snapshot-text"],
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, local
    bodies = [response.json(), protocol.structured_content, local]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        SPECS["ziwei_horoscope"].output_model.model_validate(body)
    assert bodies[0]["analysis_context"]["lunar_display"] == "2024年1月1日"
    target_basis = bodies[0]["ziwei_horoscope"]["calendar_basis"]["target"]
    assert target_basis["placement_datetime"] == "2024-02-10 00:00:00"
    assert target_basis["civil_datetime"] == "2024-02-09 23:30:00"


def test_context_scope_and_natal_linkage_match_rest_mcp_cli(monkeypatch, capsys):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = {**BIRTH, **TARGET}
    options = dict(
        as_of="2026-10-20T00:45:00+08:00",
        fields=FIELDS,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/cn/ziwei/horoscope",
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in FIELDS],
        ],
    )

    async def mcp_call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool(
                "ziwei_horoscope", {**inputs, **options}, raise_on_error=False
            )

    protocol = asyncio.run(mcp_call())
    assert response.status_code == 200, response.json()
    assert not protocol.is_error, protocol.content
    args = ["ziwei_horoscope"]
    for key, value in inputs.items():
        args.extend(["--" + key.replace("_", "-"), str(value)])
    args.extend(
        [
            "--as-of",
            options["as_of"],
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
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
