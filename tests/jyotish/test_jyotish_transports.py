"""Public Indian schemas, real REST/native MCP/CLI calls and same-run delivery."""

import asyncio
import json
from itertools import product
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import (
    execute_with_receipt,
    invoke_validated_service,
)
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish.jyotish_dasha_levels import YEAR_DAYS
from fatebridge.core.jyotish.jyotish_strength import SOURCE as STRENGTH_SOURCE
from fatebridge.core.public_output import same_public_value
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import cached_mcp_app, call_calculation

SPECS = {s.name: s for s in CATALOG}
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
        "detail": "audit",
        "fields": fields,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client, spec.name, {**payload, **options}, raise_on_error=False
            )

    protocol_result = asyncio.run(protocol())
    native = protocol_result.structured_content
    args = [spec.name]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            *([str(x) for x in value] if isinstance(value, list) else [str(value)]),
        ]
    args += [
        "--as-of",
        AS_OF,
        "--detail",
        "audit",
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


def test_1960_sofa_time_context_across_three_real_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
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


@pytest.mark.parametrize("node_mode,basis", list(product(["mean", "true"], YEAR_DAYS)))
def test_vimshottari_all_configurations_across_three_real_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    node_mode,
    basis,
) -> None:
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
        "vimshottari_dasha",
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
    assert "current_time_frozen" not in result["run_metadata"]["warnings"]
    assert result["analysis_context"]["analysis_datetime"].endswith("T00:00:00+08:00")


@pytest.mark.parametrize("node_mode", ["mean", "true"])
def test_india_birth_uncertainty_and_theme_evidence_across_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], node_mode: str
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
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


@pytest.mark.parametrize("key", ["vedic_chart", "vimshottari_dasha"])
@pytest.mark.parametrize("profile", ["santhanam_27", "raman_30"])
def test_extended_vargas_and_strength_profile_across_real_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key: str,
    profile: str,
) -> None:
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
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
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
@pytest.mark.parametrize("key", ["vedic_chart", "vimshottari_dasha"])
def test_strict_data_file_policy_rejects_fallback_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    key: str,
) -> None:
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
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client, spec.name, payload, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert native.is_error
    assert "require_data_files" in native.structured_content["error"]
    args = [spec.name]
    for name, value in payload.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    capsys.readouterr()
    code = run(args)
    captured = capsys.readouterr()
    assert code != 0
    assert "require_data_files" in captured.out + captured.err


def test_physical_state_and_dispositor_fields_project_across_three_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
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


@pytest.mark.parametrize("key", ["vedic_chart", "vimshottari_dasha"])
def test_future_time_context_and_identified_author_rules_across_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], key: str
) -> None:
    payload = {**astro_payload(), "birth_year": 2099}
    if key == "vimshottari_dasha":
        payload["analysis_year"] = 2101
    else:
        pass
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
    assert same_public_value(source, STRENGTH_SOURCE)
    assert {r["rule_id"] for r in body["india"]["rule_trace"]} >= {
        "jyotish.time_scales.v2",
        "jyotish.santhanam_solar_orb.v1",
    }


def test_discovery_has_nested_output_contracts_and_task_views() -> None:
    for key in ["vedic_chart", "vimshottari_dasha"]:
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
    schema = SPECS["vimshottari_dasha"].output_model.model_json_schema()
    assert {"Vimshottari", "DashaBirthBalance", "DashaPeriod"} <= set(schema["$defs"])


def test_as_of_date_anchor_and_declared_current_clock_use() -> None:
    spec = SPECS["vimshottari_dasha"]
    request = spec.request_model.model_validate(astro_payload())
    result = execute_with_receipt(
        spec,
        request,
        options=ExecutionOptions(as_of="2026-10-21T20:00:00Z", detail="audit"),
    )
    assert (
        result["analysis_context"]["analysis_datetime"] == "2026-10-22T00:00:00+08:00"
    )
    assert "current_time_frozen" in result["run_metadata"]["warnings"]


@pytest.mark.parametrize(
    "changes",
    [
        {"node_mode": "invalid"},
        {"divisions": [9, 9]},
        {"divisions": [99]},
        {"saptavargaja_profile": "unknown"},
        {"birth_time_uncertainty_minutes": -1},
        {"birth_time_uncertainty_minutes": 121},
        {"zodiac_type": "Tropic"},
        {"house_system": 3},
        {"year_basis": "unknown"},
        {"analysis_year": 2026, "analysis_month": 2, "analysis_day": 30},
    ],
)
def test_invalid_options_are_rejected_at_shared_schema(changes) -> None:
    with pytest.raises(ValueError):
        SPECS["vimshottari_dasha"].request_model.model_validate(
            {**astro_payload(), **changes}
        )


def test_astrology_chart_rejects_jyotish_only_options() -> None:
    for bad in (
        {"chart_variant": "india_chart"},
        {"node_mode": "true"},
        {"divisions": [9]},
        {"saptavargaja_profile": "santhanam_27"},
    ):
        with pytest.raises(ValueError):
            SPECS["astrology_chart"].request_model.model_validate(
                {**astro_payload(), **bad}
            )


@pytest.mark.parametrize("key", ["vedic_chart", "vimshottari_dasha"])
def test_additional_balas_across_real_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], key: str
) -> None:
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


def test_audit_detail_returns_full_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    response = client.post(
        "/api/astrology/vimshottari-dasha",
        json={**astro_payload(), "analysis_year": 2026},
        params={"as_of": AS_OF, "detail": "audit"},
    )
    assert response.status_code == 200
    full = response.json()
    assert len(full["vimshottari"]["timeline"]) == 9
    assert sum(len(p["antardashas"]) for p in full["vimshottari"]["timeline"]) == 81
