"""New profiles and evidence must work through REST, native MCP and CLI."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt

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
    target_year=2027,
    target_month=6,
    target_day=15,
    target_hour=12,
    target_minute=37,
    target_timezone="UTC",
)


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize(
    "key,path,inputs,fields",
    [
        ("ziwei_birth", "birth", BIRTH, ["analysis_context", "ziwei_birth"]),
        (
            "ziwei_horoscope",
            "horoscope",
            {**BIRTH, **TARGET},
            ["analysis_context", "birth_context", "ziwei_horoscope"],
        ),
        (
            "ziwei_rules",
            "rules",
            {"year_stem": "壬"},
            ["rule_catalogue", "focused_rules"],
        ),
    ],
)
def test_profiles_and_evidence_match_all_public_surfaces(
    monkeypatch, capsys, profile, key, path, inputs, fields
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = {**inputs, "rule_profile": profile}
    options = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        f"/api/cn/ziwei/{path}",
        json=inputs,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool(
                key, {**inputs, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = [key]
    for name, value in inputs.items():
        args.extend(["--" + name.replace("_", "-"), str(value)])
    args.extend(
        [
            "--as-of",
            options["as_of"],
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
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
    if key == "ziwei_horoscope":
        assert result["analysis_context"]["timezone"] == "UTC"
        assert result["analysis_context"]["analysis_datetime"] == "2027-06-15 12:37:00"
        horoscope = result[key]
        assert horoscope["ruleset"]["id"] == profile
        assert horoscope["interpretation_scope"]["scope_palace_map_supported"]
        annual = next(s for s in horoscope["scopes"] if s["scope"] == "流年")
        assert len(annual["palace_map"]) == 12
        expected = {"禄存", "擎羊", "陀罗"}
        if profile == "quanshu_v2_excerpt":
            expected |= {"天德", "月德", "丧门", "吊客", "白虎", "官府"}
        assert {s["star"] for s in annual["flowing_stars"]} == expected
        # Fixed counterexample: natal career is the annual spouse palace.
        link = next(x for x in annual["mutagen_natal_links"] if x["star"] == "天机")
        assert link["natal_palace_name"] == "官禄宫"
        assert link["scope_palace_name"] == "夫妻宫"
    elif key == "ziwei_birth":
        assert result[key]["rule_trace"]
        comparison = result[key]["sihua_source_comparison"]
        assert comparison["year_stem"] == "壬"
        assert not comparison["compared_assignments_applied"]
        assert bool(comparison["differences"]) == (profile == "iztro_2_5_8")
        assert (
            result[key]["chart_masters"]["life"]["selection_basis"]
            == "ming_palace_branch"
        )
        assert result[key]["calendar_cycles"]["status"] == "computed"
        assert all(p["changsheng12"] and p["boshi12"] for p in result[key]["palaces"])
        assert result[key]["palaces"][0]["structural_evidence"]["sanfang_sizheng"]
    else:
        assert result["focused_rules"]["sihua"]["化科"] == (
            "左辅" if profile == "iztro_2_5_8" else "天府"
        )


@pytest.mark.parametrize(
    "payload,error_fragment",
    [
        ({**BIRTH, **TARGET, "gender": "未知"}, "需要明确性别"),
        (
            {
                **BIRTH,
                **TARGET,
                "target_year": 1992,
                "target_month": 8,
                "target_day": 15,
                "target_hour": 1,
            },
            "早于出生",
        ),
        (
            {
                **BIRTH,
                **TARGET,
                "target_year": 2026,
                "target_month": 3,
                "target_day": 8,
                "target_hour": 2,
                "target_timezone": "America/New_York",
            },
            "不存在钟时",
        ),
    ],
)
def test_input_rejections_remain_native_mcp_errors(payload, error_fragment):
    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            return await client.call_tool(
                "ziwei_horoscope", payload, raise_on_error=False
            )

    result = asyncio.run(call())
    assert result.is_error
    assert error_fragment in json.dumps(result.structured_content, ensure_ascii=False)


def test_default_mcp_budget_preserves_full_palace_evidence_in_the_same_run():
    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(
                "ziwei_horoscope",
                {
                    **BIRTH,
                    **TARGET,
                    "rule_profile": "quanshu_v2_excerpt",
                    "fields": ["analysis_context", "birth_context", "ziwei_horoscope"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            reference = result.structured_content["result_delivery"]
            pieces, uri = [], reference["first_page_uri"]
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                pieces.append(page["text"])
                uri = page["next_uri"]
            text = "".join(pieces)
            assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
            complete = json.loads(text)
            assert_same_run_receipt(
                result.structured_content["run_metadata"],
                complete["run_metadata"],
                deferred_fields=reference["deferred_fields"],
            )
            assert len(complete["ziwei_horoscope"]["scopes"]) == 6
            assert all(
                len(s["palace_map"]) == 12
                for s in complete["ziwei_horoscope"]["scopes"]
            )

    asyncio.run(call())


@pytest.mark.parametrize("view", ["symbolism", "voids"])
def test_source_views_deliver_real_facts_or_verified_same_run_pages(view):
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)[view]["fields"]

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(
                "ziwei_birth",
                {
                    **BIRTH,
                    "rule_profile": "quanshu_v2_excerpt",
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            payload = result.structured_content
            if "result_delivery" in payload:
                reference = payload["result_delivery"]
                text = ""
                uri = f"fatebridge://results/{reference['result_id']}/pages/0"
                while uri:
                    page = json.loads((await client.read_resource(uri))[0].text)
                    text += page["text"]
                    uri = page["next_uri"]
                assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
                complete = json.loads(text)
                assert_same_run_receipt(
                    payload["run_metadata"],
                    complete["run_metadata"],
                    deferred_fields=reference["deferred_fields"],
                )
                payload = complete
            if view == "symbolism":
                evidence = payload["ziwei_birth"]["symbolic_properties"]
                assert len(evidence["records"]) == 16
                assert not evidence["textual_hua_terms_are_sihua"]
                assert all(
                    r["source_quote"] and r["calculation_path"]
                    for r in evidence["records"]
                )
            else:
                evidence = payload["ziwei_birth"]["void_systems"]
                assert len(evidence["xun"]["displayed_star_branches"]) == 2
                assert evidence["source_name_mapping"]["天空地劫诀中的天空"] == "地空"

    asyncio.run(call())


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_published_natal_reading_fits_default_mcp_budget_without_losing_stars(profile):
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(
                "ziwei_birth",
                {
                    **example_input(spec),
                    "rule_profile": profile,
                    "as_of": "2026-10-15T12:00:00+08:00",
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            payload = result.structured_content
            payload = await verified_inline_business(client, payload)
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


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_published_edition_view_preserves_selected_and_hypothetical_markers(profile):
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)["editions"]["fields"]

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            result = await client.call_tool(
                "ziwei_birth",
                {
                    **BIRTH,
                    "birth_year": 1990,
                    "rule_profile": profile,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            payload = result.structured_content
            payload = await verified_inline_business(client, payload)
            chart = payload["ziwei_birth"]
            assert chart["sihua"]["化忌"] == "天同"
            comparison = chart["sihua_source_comparison"]
            assert not comparison["compared_assignments_applied"]
            difference = next(
                d for d in comparison["differences"] if d["transformation"] == "化忌"
            )
            assert difference["compared_star"] == "天相"
            assert difference["compared_position"]["natal_mutagen"] is None

    asyncio.run(call())
