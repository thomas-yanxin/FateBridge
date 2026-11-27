"""REST, native MCP, and CLI parity + compact view checks."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.support.transports import call_calculation

BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    gender="男",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
)
TARGET = dict(
    analysis_year=2027,
    analysis_month=6,
    analysis_day=15,
    analysis_hour=12,
    analysis_minute=37,
    analysis_timezone="UTC",
)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize(
    "tool_name,payload_key,inputs,fields",
    [
        (
            "ziwei_birth_chart",
            "ziwei_birth",
            BIRTH,
            ["analysis_context", "ziwei_birth"],
        ),
        (
            "ziwei_timing",
            "ziwei_horoscope",
            {**BIRTH, **TARGET},
            ["analysis_context", "birth_context", "ziwei_horoscope"],
        ),
        (
            "ziwei_rules",
            "focused_rules",
            {"year_stem": "壬"},
            ["rule_catalogue", "focused_rules"],
        ),
    ],
)
def test_profiles_and_evidence_match_all_public_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    profile: str,
    tool_name: str,
    payload_key: str,
    inputs,
    fields,
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(entry for entry in CATALOG if entry.name == tool_name)
    inputs = {**inputs, "rule_profile": profile}
    options = dict(
        as_of="2026-10-22T12:00:00+08:00",
        detail="audit",
        fields=fields,
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await call_calculation(
                client, spec.name, {**inputs, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = [spec.name]
    for name, value in inputs.items():
        args.extend(["--" + name.replace("_", "-"), str(value)])
    args.extend(
        [
            "--as-of",
            options["as_of"],
            "--detail",
            "audit",
            "--fields",
            *fields,
        ]
    )
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200, rest.text
    assert not native.is_error, native.content
    assert code == 0, cli
    bodies = [
        {k: v for k, v in payload.items() if k != "run_metadata"}
        for payload in (rest.json(), native.structured_content, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    result = bodies[0]
    if payload_key == "ziwei_horoscope":
        assert result["analysis_context"]["timezone"] == "UTC"
        assert result["analysis_context"]["analysis_datetime"] == "2027-06-15 12:37:00"
        horoscope = result["ziwei_horoscope"]
        assert horoscope["ruleset"]["id"] == profile
        assert horoscope["doujun_branch"]
        annual = next(s for s in horoscope["scopes"] if s["scope"] == "流年")
        assert len(annual["palace_map"]) == 12
        expected = {
            "禄存",
            "擎羊",
            "陀罗",
            "天魁",
            "天钺",
            "文昌",
            "文曲",
            "天马",
            "红鸾",
            "天喜",
            "年解",
        }
        if profile == "quanshu_v2_excerpt":
            expected |= {"天德", "月德", "丧门", "吊客", "白虎", "官府"}
        assert set(annual["flowing_stars"].keys()) == expected
        link = next(x for x in annual["mutagen_natal_links"] if x["star"] == "天机")
        assert link["natal_palace_name"] == "官禄宫"
        assert link["scope_palace_name"] == "夫妻宫"
    elif payload_key == "ziwei_birth":
        birth = result["ziwei_birth"]
        assert "rule_trace" not in birth
        assert birth["laiyin_gong"]["ganzhi"][0] == birth["year_stem"]
        assert birth["zidou_branch"]
        assert len(birth["flying_sihua"]["matrix"]) == 12
        assert birth["chart_masters"]["life"]["selection_basis"] == "ming_palace_branch"
        assert birth["calendar_cycles"]["status"] == "computed"
        assert all(p["changsheng12"] and p["boshi12"] for p in birth["palaces"])
    else:
        assert result["focused_rules"]["sihua"]["化科"] == (
            "左辅" if profile == "iztro_2_5_8" else "天府"
        )


def test_compact_horoscope_and_birth_include_essential_fields_under_6kb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)

    birth_resp = client.post(
        "/api/ziwei/birth-chart", json=BIRTH, params=[("detail", "compact")]
    )
    assert birth_resp.status_code == 200
    assert len(birth_resp.content) < 6144
    birth_body = birth_resp.json()["ziwei_birth"]
    assert len(birth_body["reading_view"]["palaces"]) == 12
    assert birth_body["sihua"]

    timing_resp = client.post(
        "/api/ziwei/timing", json={**BIRTH, **TARGET}, params=[("detail", "compact")]
    )
    assert timing_resp.status_code == 200
    assert len(timing_resp.content) < 6144
    timing_body = timing_resp.json()["ziwei_horoscope"]
    for scope in timing_body["scopes"]:
        if scope.get("status") not in {"not_started", "unavailable"}:
            # Bug 1.3 fix: natal_palace_name & palace_ganzhi must survive compact mode!
            assert scope["natal_palace_name"]
            assert scope["palace_ganzhi"]
            assert scope["mutagen_natal_links"]
            if scope["scope"] != "小限":
                assert scope["flowing_stars"]


@pytest.mark.parametrize(
    "payload,error_fragment",
    [
        (
            {
                **BIRTH,
                **TARGET,
                "analysis_year": 1992,
                "analysis_month": 8,
                "analysis_day": 15,
                "analysis_hour": 1,
            },
            "早于出生",
        ),
        (
            {
                **BIRTH,
                **TARGET,
                "analysis_year": 2026,
                "analysis_month": 3,
                "analysis_day": 8,
                "analysis_hour": 2,
                "analysis_timezone": "America/New_York",
            },
            "nonexistent local time",
        ),
    ],
)
def test_input_rejections_remain_native_mcp_errors(
    payload: dict[str, str | int], error_fragment: str
) -> None:
    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await call_calculation(
                client, "ziwei_timing", payload, raise_on_error=False
            )

    result = asyncio.run(call())
    assert result.is_error
    assert result.structured_content is not None
    assert result.structured_content["error_code"] == "validation_error"
    assert error_fragment in result.structured_content["error"]


def test_unknown_gender_only_withholds_direction_dependent_mcp_scopes() -> None:
    async def check_scopes() -> None:
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await call_calculation(
                client,
                "ziwei_timing",
                {
                    **BIRTH,
                    **TARGET,
                    "gender": "未知",
                    "detail": "audit",
                    "fields": ["ziwei_horoscope.scopes"],
                },
            )
            assert not result.is_error
            scopes = {
                scope["scope"]: scope
                for scope in result.structured_content["ziwei_horoscope"]["scopes"]
            }
            for scope_name in ("大限", "小限"):
                assert scopes[scope_name]["status"] == "unavailable"
                assert scopes[scope_name]["unavailable_reason"] == (
                    "gender_required_for_direction"
                )
                assert scopes[scope_name]["palace_map"] == []
            for scope_name in ("流年", "流月", "流日", "流时"):
                assert len(scopes[scope_name]["palace_map"]) == 12
                assert len(scopes[scope_name]["mutagen_natal_links"]) == 4

    asyncio.run(check_scopes())


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_published_natal_reading_fits_default_mcp_budget_without_losing_stars(
    profile: str,
) -> None:
    spec = next(s for s in CATALOG if s.name == "ziwei_birth_chart")

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await call_calculation(
                client,
                "ziwei_birth_chart",
                {
                    **example_input(spec),
                    "rule_profile": profile,
                    "as_of": "2026-10-15T12:00:00+08:00",
                    "detail": "audit",
                    "fields": suggested_fields(spec),
                },
            )
            assert not result.is_error
            payload = await verified_inline_business(client, result.structured_content)
            reading = payload["ziwei_birth"]["reading_view"]
            assert len(reading["palaces"]) == 12
            assert sum(len(p["stars"]) for p in reading["palaces"]) == (
                67 if profile == "quanshu_v2_excerpt" else 66
            )
            assert reading["distinct_star_count"] == 66
            assert (
                sum(
                    "mutagen" in star for p in reading["palaces"] for star in p["stars"]
                )
                == 4
            )
            assert reading["null_star_fields_omitted"] == ["brightness", "mutagen"]
            assert all(
                len(p["sanfang_sizheng_branches"]) == 4 for p in reading["palaces"]
            )

    asyncio.run(call())
