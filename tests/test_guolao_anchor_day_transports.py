"""Real REST, native MCP and CLI parity for the new source-day policies."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.guolao_anchor_days import DAY_RULESET, POLICIES
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

AS_OF = "2026-10-23T12:00:00+08:00"


def payload(policy):
    return dict(
        name="虚构安命日界三端验收",
        birth_year=2000,
        birth_month=7,
        birth_day=7,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC+08:00",
        birth_longitude=116.4,
        birth_latitude=40,
        use_true_solar_time=True,
        guolao_seasonal_anchor_policy=policy,
    )


@pytest.mark.parametrize("key", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("policy", POLICIES[1:])
@pytest.mark.parametrize("target", [None, "2027-06-01T00:00:00+08:00"])
def test_day_policy_and_alias_match_across_all_real_transports(
    monkeypatch, capsys, key, policy, target
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == key)
    args = payload(policy)
    if key == "astro_chart":
        args["chart_variant"] = "guolao_chart"
    if target:
        args["analysis_datetime"] = target
    fields = [
        "person_info",
        "guolao",
        "planets",
        "interpretation",
        "interpretation_evidence",
    ]
    options = dict(
        as_of=AS_OF,
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=args,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(create_mcp_app()) as client:
            tools = await client.list_tools()
            tool = next(t for t in tools if t.name == spec.tool_name)
            assert "guolao_seasonal_anchor_policy" in tool.input_schema["properties"]
            return await client.call_tool(
                spec.tool_name, {**args, **options}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    cli_args = [spec.tool_name]
    for name, value in args.items():
        cli_args += ["--" + name.replace("_", "-"), str(value)]
    cli_args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(cli_args) == 0
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200, rest.text
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [rest.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    g = bodies[0]["guolao"]
    life = g["life_palace"]
    assert g["profile"]["ruleset_id"] == DAY_RULESET and life["branch"] == "卯"
    assert life["seasonal_anchor_policy"] == policy
    assert (
        life["seasonal_anchor_evidence"]["policy_selected_by_prediction_fit"] is False
    )
    assert "真太阳日" in bodies[0]["interpretation"]["core_identity"]
    assert (
        bodies[0]["interpretation_evidence"]["core_identity"]["policy_id"]
        == "guolao_calculation_reading_v3"
    )
    assert set(bodies[0]["interpretation"]) == set(bodies[0]["interpretation_evidence"])
    if target:
        assert g["timing"]["small_limit"]["life_branch"] == life["branch"]
    else:
        assert g["timing"] == {"status": "not_requested"}


def test_both_public_request_schemas_publish_exactly_the_declared_enum_and_nullable_default():
    for model in [AstroGuolaoRequest, AstroChartPolyRequest]:
        field = model.model_json_schema()["properties"]["guolao_seasonal_anchor_policy"]
        assert field["default"] is None
        assert field["anyOf"][0]["enum"] == list(POLICIES)


def test_request_without_required_solar_clock_fails_in_rest_mcp_and_cli(
    monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "astro_guolao")
    args = payload(POLICIES[1])
    args["use_true_solar_time"] = False
    rest = TestClient(api.app).post(spec.rest_path, json=args)
    assert rest.status_code in {400, 422}

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(spec.tool_name, args, raise_on_error=False)

    assert asyncio.run(protocol()).is_error
    cli_args = [spec.tool_name]
    for key, value in args.items():
        cli_args += ["--" + key.replace("_", "-"), str(value)]
    capsys.readouterr()
    assert run(cli_args) != 0
    output = capsys.readouterr().out
    assert not output or "guolao_research_v8" not in output


def test_day_edge_evidence_survives_complete_same_run_delivery(monkeypatch, tmp_path):
    from fatebridge.application import result_delivery as delivery
    from fatebridge.core import guolao

    store = delivery.ResultStore(tmp_path / "results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    shaped = client.post(
        "/api/astro/guolao",
        json=payload(POLICIES[2]),
        params={"as_of": AS_OF, "response_char_limit": 8192},
    )
    assert shaped.status_code == 200, shaped.text
    body = shaped.json()
    ref = body["result_delivery"]

    def must_not_recalculate(*args, **kwargs):
        pytest.fail("reading day-edge evidence must reuse the original calculation")

    monkeypatch.setattr(guolao, "build_chart", must_not_recalculate)
    chunks = []
    offset = 0
    while True:
        part = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert part.status_code == 200, part.text
        page = part.json()
        chunks.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    raw = "".join(chunks)
    assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
    full = json.loads(raw)
    assert full["run_metadata"]["run_id"] == body["run_metadata"]["run_id"]
    evidence = full["guolao"]["life_palace"]["seasonal_anchor_evidence"]
    assert evidence["policy"] == POLICIES[2]
    assert len(evidence["day_edge_brackets"]) == 2
    assert evidence["same_birth_source_cohort_checked"] is True
    assert evidence["historical_local_day_boundary_accepted"] is False
