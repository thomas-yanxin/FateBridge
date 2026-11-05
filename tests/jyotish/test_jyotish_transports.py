"""Public Indian schemas, real REST/native MCP/CLI calls and same-run delivery."""

import asyncio
import hashlib
import json
from itertools import product

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish import YEAR_DAYS
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload

SPECS = {s.key: s for s in CATALOG}
AS_OF = "2026-10-22T12:00:00+08:00"


def call_surfaces(monkeypatch, capsys, key, payload, fields):
    spec = SPECS[key]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
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
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    protocol_result = asyncio.run(protocol())
    native = protocol_result.structured_content
    assert native == json.loads(protocol_result.content[0].text)
    args = [spec.tool_name]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            *([str(x) for x in value] if isinstance(value, list) else [str(value)]),
        ]
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
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol_result.is_error, native
    assert code == 0, cli
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    return response.json()


def test_1960_sofa_time_context_across_three_real_surfaces(monkeypatch, capsys):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        {
            **astro_payload(),
            "birth_year": 1960,
            "birth_month": 6,
            "birth_day": 15,
            "birth_hour": 12,
            "birth_minute": 34,
            "birth_timezone": "UTC",
        },
        ["india.profile"],
    )
    profile = result["india"]["profile"]
    assert profile["julian_day_utc"] is not None
    assert profile["time_scale_context"]["method"].startswith("SOFA_1960")
    assert profile["time_scale_context"]["houses_timescale"] == "UT1_model_estimate"
    assert profile["time_scale_context"]["historical_utc_source"] == (
        "https://www.iausofa.org/2023-10-11c"
    )


@pytest.mark.parametrize("node_mode,basis", list(product(["mean", "true"], YEAR_DAYS)))
def test_vimshottari_all_configurations_across_three_real_surfaces(
    monkeypatch, capsys, node_mode, basis
):
    payload = {
        **astro_payload(),
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 22,
        "analysis_hour": 0,
        "analysis_minute": 0,
        "year_basis": basis,
        "node_mode": node_mode,
        "divisions": [9, 10],
    }
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        payload,
        [
            "analysis_context",
            "vimshottari",
            "india.profile",
            "india.charts",
            "india.rulesets",
            "india.rule_trace",
        ],
    )
    assert result["vimshottari"]["year_days"] == YEAR_DAYS[basis]
    assert not result["run_metadata"]["determinism"]["uses_current_time"]
    assert result["analysis_context"]["analysis_datetime"].endswith("T00:00:00+08:00")


@pytest.mark.parametrize("node_mode", ["mean", "true"])
def test_india_birth_uncertainty_and_theme_evidence_across_surfaces(
    monkeypatch, capsys, node_mode
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        {
            **astro_payload(),
            "node_mode": node_mode,
            "divisions": [9, 10],
            "birth_time_uncertainty_minutes": 2,
        },
        ["india"],
    )
    assert result["india"]["birth_time_sensitivity"]["sample_count"] == 9
    assert result["india"]["topic_evidence"]["career"]["factors"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
@pytest.mark.parametrize("profile", ["santhanam_27", "raman_30"])
def test_extended_vargas_and_strength_profile_across_real_surfaces(
    monkeypatch, capsys, key, profile
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {
            **astro_payload(),
            "divisions": [2, 3, 7, 9, 10, 12, 30],
            "saptavargaja_profile": profile,
        },
        [
            "india.charts",
            "india.strengths.sthana_bala",
            "india.profile",
            "india.rule_trace",
        ],
    )
    india = result["india"]
    assert set(india["charts"]) == {"D1", "D2", "D3", "D7", "D9", "D10", "D12", "D30"}
    assert india["strengths"]["sthana_bala"]["profile"]["id"] == profile
    assert india["profile"]["saptavargaja_profile"] == profile
    for point in [
        india["charts"]["D30"]["ascendant"],
        *india["charts"]["D30"]["planets"],
    ]:
        assert point["longitude"] is None
        assert point["degree_in_sign"] is None


def test_nested_strength_summary_field_projects_across_real_surfaces(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        astro_payload(),
        [
            "india.strengths.sthana_bala.summary.Sun.total_virupa",
            "india.strengths.sthana_bala.profile",
        ],
    )
    strength = result["india"]["strengths"]["sthana_bala"]
    assert set(strength["summary"]["Sun"]) == {"total_virupa"}
    assert strength["summary"]["Sun"]["total_virupa"] > 0
    assert strength["profile"]["id"] == "santhanam_27"


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_strict_data_file_policy_rejects_fallback_on_all_surfaces(
    monkeypatch, capsys, tmp_path, key
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = SPECS[key]
    payload = {**astro_payload(), "ephemeris_policy": "require_data_files"}
    response = TestClient(api.app).post(spec.rest_path, json=payload)
    assert "require_data_files" in response.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(spec.tool_name, payload, raise_on_error=False)

    native = asyncio.run(protocol())
    assert native.is_error
    assert "require_data_files" in native.content[0].text
    args = [spec.tool_name]
    for name, value in payload.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    capsys.readouterr()
    code = run(args)
    captured = capsys.readouterr()
    assert code != 0
    assert "require_data_files" in captured.out + captured.err


def test_physical_state_and_dispositor_fields_project_across_three_surfaces(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        astro_payload(),
        [
            "india.profile.ephemeris_quality",
            "india.charts.D1.planets",
            "india.rule_trace",
        ],
    )
    assert (
        result["india"]["charts"]["D1"]["planets"][0]["physical_state"][
            "degree_condition"
        ]["uchcha_bala"]["unit"]
        == "virupa"
    )


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_future_time_context_and_identified_author_rules_across_surfaces(
    monkeypatch, capsys, key
):
    payload = {**astro_payload(), "birth_year": 2099}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2101
    body = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile",
            "india.charts.D1.planets",
            "india.rulesets",
            "india.rule_trace",
        ],
    )
    profile = body["india"]["profile"]
    assert (
        profile["time_scale_context"]["future_leap_seconds_assumed_unchanged"] is True
    )
    assert (
        profile["julian_day_tt"] - profile["julian_day_utc"]
    ) * 86400 == pytest.approx(69.184, abs=0.00005)
    mercury = next(
        p for p in body["india"]["charts"]["D1"]["planets"] if p["id"] == "Mercury"
    )
    condition = mercury["physical_state"]["combustion"]
    assert condition["source_layer"] == "translator_commentary"
    source = next(
        s for s in body["india"]["rulesets"] if s["id"] == condition["source_id"]
    )
    assert (
        source["sha256"]
        == "13609f1af89541e070c798b8c70c6bfd74a8b9a71a71388913bf898e9f9ddf3f"
    )
    assert {r["rule_id"] for r in body["india"]["rule_trace"]} >= {
        "jyotish.time_scales.v2",
        "jyotish.santhanam_solar_orb.v1",
    }


def test_discovery_has_nested_output_contracts_and_task_views():
    for key in ["astro_india", "astro_vimshottari"]:
        description = describe_spec(SPECS[key])
        assert description["evidence_views"]
        assert description["call_guidance"]
        schema = SPECS[key].output_model.model_json_schema()
        assert {"JyotishProfile", "VargaCharts", "VargaChart", "Nakshatra"} <= set(
            schema["$defs"]
        )
        assert {"SthanaBala", "SthanaValues", "JyotishStrengths"} <= set(
            schema["$defs"]
        )
    schema = SPECS["astro_vimshottari"].output_model.model_json_schema()
    assert {"Vimshottari", "DashaBirthBalance", "DashaPeriod"} <= set(schema["$defs"])


def test_published_indian_contract_files_match_live_native_mcp_schemas():
    from scripts import build_codex_call_contracts as builder

    files = asyncio.run(builder.render_files())
    for name in ("astro_india_chart.json", "astro_vimshottari.json"):
        assert (builder.TARGET / name).read_text() == files[name]


def test_as_of_date_anchor_and_declared_current_clock_use():
    spec = SPECS["astro_vimshottari"]
    request = spec.request_model.model_validate(astro_payload())
    result = execute_tool(
        spec, request, options=ExecutionOptions(as_of="2026-10-21T20:00:00Z")
    )
    assert (
        result["analysis_context"]["analysis_datetime"] == "2026-10-22T00:00:00+08:00"
    )
    assert result["run_metadata"]["determinism"]["uses_current_time"]


@pytest.mark.parametrize(
    "changes",
    [
        {"node_mode": "invalid"},
        {"divisions": [9, 9]},
        {"divisions": [60]},
        {"saptavargaja_profile": "unknown"},
        {"birth_time_uncertainty_minutes": -1},
        {"birth_time_uncertainty_minutes": 121},
        {"zodiacal": 0},
        {"hsys": 3},
        {"year_basis": "unknown"},
        {"analysis_year": 2026, "analysis_month": 2, "analysis_day": 30},
    ],
)
def test_invalid_options_are_rejected_at_shared_schema(changes):
    with pytest.raises(ValueError):
        SPECS["astro_vimshottari"].request_model.model_validate(
            {**astro_payload(), **changes}
        )


def test_polymorphic_india_matches_dedicated_service_and_other_variants_reject_options():
    payload = {**astro_payload(), "node_mode": "true", "divisions": [9]}
    dedicated = execute_tool(
        SPECS["astro_india"],
        SPECS["astro_india"].request_model.model_validate(payload),
        include_metadata=False,
    )
    poly = execute_tool(
        SPECS["astro_chart"],
        SPECS["astro_chart"].request_model.model_validate(
            {**payload, "chart_variant": "india_chart"}
        ),
        include_metadata=False,
    )
    assert poly == dedicated
    with pytest.raises(ValueError):
        SPECS["astro_chart"].request_model.model_validate(payload)


def test_non_indian_chart_accepts_protocol_materialized_neutral_defaults():
    spec = SPECS["astro_chart"]
    plain = execute_tool(
        spec, spec.request_model.model_validate(astro_payload()), include_metadata=False
    )
    request = spec.request_model.model_validate(
        {
            **astro_payload(),
            "node_mode": "mean",
            "divisions": [9, 10],
            "birth_time_uncertainty_minutes": None,
            "saptavargaja_profile": "santhanam_27",
        }
    )
    assert execute_tool(spec, request, include_metadata=False) == plain


def test_non_indian_chart_rejects_custom_saptavargaja_profile():
    with pytest.raises(ValueError, match="india_chart"):
        SPECS["astro_chart"].request_model.model_validate(
            {**astro_payload(), "saptavargaja_profile": "raman_30"}
        )


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_additional_balas_across_real_surfaces(monkeypatch, capsys, key):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        astro_payload(),
        [
            "india.strengths",
            "india.birth_time_sensitivity",
            "india.rulesets",
            "india.rule_trace",
        ],
    )
    strengths = result["india"]["strengths"]
    assert strengths["shadbala_assessment"]["total_virupa"] is None
    assert (
        "cheshta_bala_five_star_mean_model"
        in strengths["shadbala_assessment"]["missing"]
    )
    assert strengths["dig_bala"]["basis"]["angles"]["Midheaven"] is not None
    assert strengths["naisargika_bala"]["summary"]["Sun"] == 60
    drik = strengths["drik_bala"]
    assert (
        drik["nature_context"]["mercury_status"]
        == "association_predicate_not_adjudicated"
    )
    assert len(drik["scenarios"]) == 2 * len(drik["nature_context"]["moon_options"])
    sources = {source["id"] for source in result["india"]["rulesets"]}
    for name in ("dig_bala", "naisargika_bala", "drik_bala"):
        assert strengths[name]["source_id"] in sources
    kala = strengths["kala_bala"]
    assert len(kala["components"]) == 9
    assert kala["components"]["nathonnatha_bala"]["summary"]["Mercury"] == 60
    assert kala["solar_events"]["definition"].startswith("Swiss BIT_HINDU_RISING")
    assert "natal birth instant" in kala["temporal_scope"]
    motion = strengths["cheshta_bala"]
    assert motion["status"] == "partial_luminaries_only"
    assert (
        motion["summary"]["Sun"] == kala["components"]["ayana_bala"]["summary"]["Sun"]
    )
    assert motion["summary"]["Mars"] is None


def test_full_timeline_uses_same_run_pagination_and_hash(monkeypatch, tmp_path):
    from fatebridge.application import result_delivery as delivery
    from fatebridge.services import jyotish

    store = delivery.ResultStore(tmp_path / "private-results")
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
        "/api/astro/vimshottari",
        json={**astro_payload(), "analysis_year": 2026},
        params={
            "include_snapshot_text": "false",
            "as_of": AS_OF,
            "response_char_limit": 8192,
        },
    )
    assert response.status_code == 200
    shaped = response.json()
    ref = shaped["result_delivery"]

    def must_not_recalculate(*args, **kwargs):
        pytest.fail("reading the saved complete result must not recalculate")

    monkeypatch.setattr(jyotish, "calculate_vimshottari", must_not_recalculate)
    chunks = []
    offset = 0
    while True:
        page_response = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert page_response.status_code == 200
        page = page_response.json()
        chunks.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    text = "".join(chunks)
    assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
    full = json.loads(text)
    assert full["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]
    assert len(full["vimshottari"]["timeline"]) == 9
    assert sum(len(p["antardashas"]) for p in full["vimshottari"]["timeline"]) == 81
