"""Real REST, native MCP, CLI and complete same-run delivery for Guolao."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload

SPEC = next(s for s in CATALOG if s.key == "astro_guolao")
AS_OF = "2026-10-22T12:00:00+08:00"


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("hsys,zodiacal", [(0, 0), (3, 1)])
@pytest.mark.parametrize("target", [None, "2027-06-01T00:00:00+08:00"])
def test_guolao_across_three_real_surfaces(
    monkeypatch, capsys, solar, hsys, zodiacal, target
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = {
        **astro_payload(),
        "use_true_solar_time": solar,
        "hsys": hsys,
        "zodiacal": zodiacal,
    }
    if target is not None:
        payload["analysis_datetime"] = target
    fields = ["person_info", "guolao", "interpretation", "interpretation_evidence"]
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        SPEC.rest_path,
        json=payload,
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
            return await client.call_tool(
                SPEC.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    args = [SPEC.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
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
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert native.structured_content == json.loads(native.content[0].text)
    bodies = [
        {k: v for k, v in x.items() if k != "run_metadata"}
        for x in [response.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert len(bodies[0]["guolao"]["bodies"]) == 11
    assert set(bodies[0]["interpretation_evidence"]) == set(bodies[0]["interpretation"])
    for pattern in bodies[0]["guolao"]["moira_patterns"]:
        assert pattern["rule_id"]
        assert pattern["evidence"]["condition_satisfied"]
        assert not pattern["evidence"]["classical_acceptance"]
    timing = bodies[0]["guolao"]["timing"]
    if target is not None:
        assert timing["small_limit"]["target_year_branch"] == "未"
        assert len(timing["transit_bodies"]) == 11
    else:
        assert timing == {"status": "not_requested"}


@pytest.mark.parametrize("target", [None, "2027-06-01T00:00:00+08:00"])
def test_discovery_and_polymorphic_contract_expose_research_limits(target):
    description = describe_spec(SPEC)
    assert description["evidence_views"]
    assert description["call_guidance"]
    definitions = SPEC.output_model.model_json_schema()["$defs"]
    assert {
        "GuolaoBody",
        "GuolaoMansion",
        "GuolaoProfile",
        "GuolaoRuleTrace",
        "GuolaoValidation",
        "GuolaoGodPositions",
        "GuolaoPurpleModelAudit",
        "GuolaoSmallLimit",
        "GuolaoTiming",
        "GuolaoTargetProfile",
    } <= set(definitions)
    poly = next(s for s in CATALOG if s.key == "astro_chart")
    payload = {**astro_payload(), "analysis_datetime": target}
    dedicated = execute_tool(
        SPEC, SPEC.request_model.model_validate(payload), include_metadata=False
    )
    generic = execute_tool(
        poly,
        poly.request_model.model_validate({**payload, "chart_variant": "guolao_chart"}),
        include_metadata=False,
    )
    assert generic == dedicated


@pytest.mark.parametrize(
    "target,basis",
    [
        (None, None),
        ("2027-06-01T00:00:00+08:00", None),
        ("2027-06-01T00:00:00+08:00", "jie_month"),
        ("2027-06-01T00:00:00+08:00", "chinese_lunar_utc8"),
    ],
)
def test_complete_result_delivery_reads_same_run_without_recalculation(
    monkeypatch, tmp_path, target, basis
):
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
    response = client.post(
        SPEC.rest_path,
        json={
            **astro_payload(),
            "analysis_datetime": target,
            "guolao_month_basis": basis,
        },
        params={"as_of": AS_OF, "response_char_limit": 8192},
    )
    assert response.status_code == 200, response.text
    shaped = response.json()
    ref = shaped["result_delivery"]

    def must_not_recalculate(*args, **kwargs):
        pytest.fail("reading this run must not recalculate the chart")

    monkeypatch.setattr(guolao, "build_chart", must_not_recalculate)
    chunks = []
    offset = 0
    while True:
        part = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert part.status_code == 200, part.text
        body = part.json()
        chunks.append(body["text"])
        if body["next_offset"] is None:
            break
        offset = body["next_offset"]
    raw = "".join(chunks)
    assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
    full = json.loads(raw)
    assert full["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]
    assert len(full["guolao"]["bodies"]) == 11
    if target is not None:
        assert len(full["guolao"]["timing"]["transit_bodies"]) == 11
    if basis is not None:
        assert full["guolao"]["timing"]["month_limit"]["month_basis"] == basis
        assert "month_limit" in full["interpretation_evidence"]


def test_nested_target_projection_preserves_contract_and_current_run_evidence(
    monkeypatch,
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = [
        "guolao.timing.analysis_datetime",
        "guolao.timing.small_limit.branch",
        "guolao.timing.transit_bodies",
        "guolao.timing.profile.future_leap_seconds_assumed_unchanged",
        "guolao.rule_trace",
        "guolao.validation",
        "interpretation",
    ]
    response = TestClient(api.app).post(
        SPEC.rest_path,
        json={**astro_payload(), "analysis_datetime": "2027-06-01T00:00:00+08:00"},
        params=[
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text
    projected = response.json()
    timing = projected["guolao"]["timing"]
    assert timing["small_limit"] == {"branch": "未"}
    assert len(timing["transit_bodies"]) == 11
    assert all(b["mansion"]["su28"] for b in timing["transit_bodies"])
    assert "小限在未" in projected["interpretation"]["timing"]
