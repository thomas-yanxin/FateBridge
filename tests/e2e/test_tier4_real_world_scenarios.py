"""Tier 4 opaque-box E2E tests for realistic multi-tool consultation workflows."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import (
    AUGMENTED_TOOL_INPUTS,
    EXTRA_DOMAIN_INPUTS,
    assert_dotted_path_restored,
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_mcp_tool,
    call_python_run,
    call_rest_get,
    call_rest_post,
    find_bloat_keys,
    has_dotted_path,
    strip_run_metadata,
)

DEMO_NATIVE_SUBJECT: dict[str, Any] = {
    "name": "演示甲",
    "gender": "male",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_place": "北京",
    "birth_longitude": 116.4074,
    "birth_latitude": 39.9042,
    "timezone": "Asia/Shanghai",
}

DEMO_CONSULTATION_CONTEXT: dict[str, Any] = {
    "year": 2026,
    "month": 10,
    "day": 12,
    "hour": 14,
    "minute": 30,
    "place": "北京",
    "longitude": 116.4074,
    "latitude": 39.9042,
    "timezone": "Asia/Shanghai",
}


def _assert_clean_run_metadata(
    payload: dict[str, Any],
    *,
    tool_name: str,
    as_of: str,
    expect_omitted: bool | None = None,
) -> list[str]:
    assert find_bloat_keys(payload) == [], f"Unexpected bloat keys in {tool_name}"
    meta = payload.get("run_metadata")
    assert isinstance(meta, dict), f"Missing run_metadata for {tool_name}"
    assert meta.get("tool_name") == tool_name
    assert isinstance(meta.get("duration_ms"), (int, float))
    assert meta["duration_ms"] >= 0
    replay = meta.get("replay")
    assert isinstance(replay, dict), f"Missing replay metadata for {tool_name}"
    assert replay.get("as_of") == as_of
    assert isinstance(replay.get("overrides"), dict)
    assert isinstance(replay.get("requires_original_input"), bool)

    omitted = meta.get("omitted_fields")
    if expect_omitted is True:
        assert (
            isinstance(omitted, list) and len(omitted) > 0
        ), f"Expected {tool_name} default payload to populate run_metadata.omitted_fields"
    elif expect_omitted is False:
        assert (
            not omitted
        ), f"Expected {tool_name} response to omit/clear omitted_fields, got {omitted!r}"
    return list(omitted) if isinstance(omitted, list) else []


def _verify_consultation_drilldown(
    tool_name: str,
    inputs: dict[str, Any],
    *,
    specs: dict[str, dict[str, Any]],
    as_of: str,
    default_payload: dict[str, Any] | None = None,
    preferred_view: str | None = None,
    projection_fields: list[str] | None = None,
    expect_heavy_omissions: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run (b) default -> (c) include drill-down -> (d) include=['*'] -> (e) fields."""
    if default_payload is None:
        default_res = call_python_run(tool_name, inputs, as_of=as_of)
        assert default_res.ok, default_res.payload
        default_payload = default_res.payload

    default_omitted = _assert_clean_run_metadata(
        default_payload,
        tool_name=tool_name,
        as_of=as_of,
        expect_omitted=True if expect_heavy_omissions else None,
    )

    full_res = call_python_run(tool_name, inputs, as_of=as_of, include=["*"])
    assert full_res.ok, full_res.payload
    full_payload = full_res.payload
    _assert_clean_run_metadata(
        full_payload,
        tool_name=tool_name,
        as_of=as_of,
        expect_omitted=False,
    )
    assert_isomorphic_subset(default_payload, full_payload)

    for omitted_path in default_omitted:
        assert not has_dotted_path(
            default_payload, omitted_path
        ), f"{tool_name}: {omitted_path!r} should be omitted from default payload"
        assert has_dotted_path(
            full_payload, omitted_path
        ), f"{tool_name}: {omitted_path!r} missing from include=['*']"

    views = specs[tool_name].get("evidence_views") or {}
    if preferred_view is not None:
        assert preferred_view in views, (
            f"{tool_name}: expected evidence view {preferred_view!r} "
            f"not in {sorted(views)}"
        )
        view_name = preferred_view
        view_fields = list(views[view_name]["fields"])
        assert view_fields, f"{tool_name}: view {view_name!r} has empty fields"
        view_res = call_python_run(tool_name, inputs, as_of=as_of, include=[view_name])
        assert view_res.ok, view_res.payload
        view_payload = view_res.payload
        view_omitted = _assert_clean_run_metadata(
            view_payload, tool_name=tool_name, as_of=as_of
        )
        assert_isomorphic_subset(default_payload, view_payload)
        assert_isomorphic_subset(view_payload, full_payload)
        for field_path in view_fields:
            assert has_dotted_path(
                full_payload, field_path
            ), f"{tool_name}: view {view_name!r} field {field_path!r} missing in full payload"
            assert has_dotted_path(
                view_payload, field_path
            ), f"{tool_name}: view {view_name!r} field {field_path!r} missing"
            assert field_path not in view_omitted

    if default_omitted:
        target_path = default_omitted[0]
        path_res = call_python_run(
            tool_name, inputs, as_of=as_of, include=[target_path]
        )
        assert path_res.ok, path_res.payload
        path_payload = path_res.payload
        path_omitted = _assert_clean_run_metadata(
            path_payload, tool_name=tool_name, as_of=as_of
        )
        assert_dotted_path_restored(
            default_payload, path_payload, full_payload, target_path
        )
        assert target_path not in path_omitted
        assert_isomorphic_subset(default_payload, path_payload)
        assert_isomorphic_subset(path_payload, full_payload)

    if projection_fields is not None:
        selected_fields = list(projection_fields)
    else:
        selected_fields = sorted(k for k in full_payload if k != "run_metadata")[:2]
    assert selected_fields, f"No valid projection fields resolved for {tool_name}"
    for field_path in selected_fields:
        assert has_dotted_path(
            full_payload, field_path
        ), f"{tool_name}: projection field {field_path!r} missing in full payload"
    proj_res = call_python_run(tool_name, inputs, as_of=as_of, fields=selected_fields)
    assert proj_res.ok, proj_res.payload
    proj_payload = proj_res.payload
    _assert_clean_run_metadata(
        proj_payload,
        tool_name=tool_name,
        as_of=as_of,
        expect_omitted=False,
    )
    expected_top_keys = {field.split(".")[0] for field in selected_fields}
    assert set(strip_run_metadata(proj_payload)) == expected_top_keys
    for field_path in selected_fields:
        assert has_dotted_path(proj_payload, field_path)
    assert_isomorphic_subset(proj_payload, full_payload)

    return default_payload, full_payload


# ---------------------------------------------------------------------------
# Scenario 1: BaZi Natal & Multi-Horizon Timing Consultation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_1_bazi_natal_and_multi_horizon_timing(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    scenario_tools = (
        "bazi_overview",
        "bazi_birth_chart",
        "bazi_career",
        "bazi_timing",
        "bazi_luck_cycles",
        "bazi_yearly_timing",
    )
    discovered_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": list(scenario_tools), "detail": "full"},
    )
    assert discovered_outcome.ok, discovered_outcome.payload
    discovered = discovered_outcome.payload
    assert discovered["matched_count"] == len(scenario_tools)
    discovered_by_name = {entry["tool"]: entry for entry in discovered["tools"]}
    for tool_name in scenario_tools:
        assert tool_name in discovered_by_name

    batch_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "subjects": {"client": DEMO_NATIVE_SUBJECT},
            "context": DEMO_CONSULTATION_CONTEXT,
            "defaults": {"zi_hour_policy": "day_rollover_at_23"},
            "as_of": e2e_as_of,
            "calls": [
                {"id": tool_name, "tool": tool_name, "subject": "client"}
                for tool_name in scenario_tools
            ],
        },
    )
    assert batch_outcome.ok, batch_outcome.payload
    assert batch_outcome.payload["status"] == "ok"
    assert batch_outcome.payload["succeeded"] == len(scenario_tools)
    batch_defaults = {
        item["id"]: item["result"] for item in batch_outcome.payload["results"]
    }

    preferred_views: dict[str, str | None] = {
        "bazi_overview": "force_adjudication",
        "bazi_birth_chart": "calendar_basis",
        "bazi_career": "target_year",
        "bazi_timing": "interactions",
        "bazi_luck_cycles": "birth_time_sensitivity",
        "bazi_yearly_timing": None,
    }
    projection_map: dict[str, list[str]] = {
        "bazi_overview": ["four_pillars", "day_master.strength", "favorable_elements"],
        "bazi_birth_chart": ["bazi_birth.four_pillars", "bazi_birth.day_master"],
        "bazi_career": [
            "career_analysis.timing_context",
            "career_analysis.topic_facts.day_master",
        ],
        "bazi_timing": ["dayun", "liunian", "summary"],
        "bazi_luck_cycles": ["dayun", "element_effects"],
        "bazi_yearly_timing": ["liunian", "element_effects"],
    }
    heavy_tools = {"bazi_overview", "bazi_birth_chart", "bazi_timing"}

    batch_matched_tools = {"bazi_overview", "bazi_birth_chart", "bazi_career"}
    for tool_name in scenario_tools:
        inputs = augmented_inputs_for(tool_name, all_tool_specs)
        batch_default = batch_defaults[tool_name]
        _assert_clean_run_metadata(
            batch_default,
            tool_name=tool_name,
            as_of=e2e_as_of,
            expect_omitted=True if tool_name in heavy_tools else None,
        )
        if tool_name in batch_matched_tools:
            inputs["gender"] = DEMO_NATIVE_SUBJECT["gender"]
        _verify_consultation_drilldown(
            tool_name,
            inputs,
            specs=all_tool_specs,
            as_of=e2e_as_of,
            default_payload=(
                batch_default if tool_name in batch_matched_tools else None
            ),
            preferred_view=preferred_views[tool_name],
            projection_fields=projection_map[tool_name],
            expect_heavy_omissions=tool_name in heavy_tools,
        )


# ---------------------------------------------------------------------------
# Scenario 2: Ziwei Natal & Horoscope Consultation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_2_ziwei_natal_and_horoscope_consultation(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    scenario_tools = ("ziwei_birth_chart", "ziwei_timing", "ziwei_rules")
    discover_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": list(scenario_tools), "detail": "full"},
    )
    assert discover_outcome.ok, discover_outcome.payload
    assert discover_outcome.payload["matched_count"] == 3

    batch_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "subjects": {"client": DEMO_NATIVE_SUBJECT},
            "context": DEMO_CONSULTATION_CONTEXT,
            "as_of": e2e_as_of,
            "calls": [
                {
                    "id": "ziwei_birth_chart",
                    "tool": "ziwei_birth_chart",
                    "subject": "client",
                },
                {"id": "ziwei_timing", "tool": "ziwei_timing", "subject": "client"},
            ],
        },
    )
    assert batch_outcome.ok, batch_outcome.payload
    assert batch_outcome.payload["status"] == "ok"
    for item in batch_outcome.payload["results"]:
        _assert_clean_run_metadata(
            item["result"],
            tool_name=item["id"],
            as_of=e2e_as_of,
            expect_omitted=True,
        )

    _verify_consultation_drilldown(
        "ziwei_birth_chart",
        augmented_inputs_for("ziwei_birth_chart", all_tool_specs),
        specs=all_tool_specs,
        as_of=e2e_as_of,
        preferred_view="palace_sihua",
        projection_fields=["ziwei_birth.ruleset", "ziwei_birth.year_stem"],
        expect_heavy_omissions=True,
    )
    _verify_consultation_drilldown(
        "ziwei_timing",
        augmented_inputs_for("ziwei_timing", all_tool_specs),
        specs=all_tool_specs,
        as_of=e2e_as_of,
        preferred_view="flowing_stars",
        projection_fields=["ziwei_horoscope.ruleset", "ziwei_horoscope.nominal_age"],
        expect_heavy_omissions=True,
    )
    _verify_consultation_drilldown(
        "ziwei_rules",
        augmented_inputs_for("ziwei_rules", all_tool_specs),
        specs=all_tool_specs,
        as_of=e2e_as_of,
        preferred_view="sihua_source",
        projection_fields=["focused_rules", "rule_catalogue.ruleset"],
        expect_heavy_omissions=False,
    )


# ---------------------------------------------------------------------------
# Scenario 3: Fengshui Site, Natal House & Annual/Monthly Assessment
# ---------------------------------------------------------------------------


def test_scenario_3_fengshui_site_and_annual_monthly_assessment(
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    discover_outcome = call_rest_get(
        rest_client,
        "/api/tools",
        params={"family": "fengshui", "detail": "full"},
    )
    assert discover_outcome.ok, discover_outcome.payload
    discovered_names = {entry["tool"] for entry in discover_outcome.payload["tools"]}

    scenario_tools = (
        "fengshui_directions",
        "fengshui_minggua",
        "fengshui_bazhai",
        "fengshui_xuankong_house_chart",
        "fengshui_assess",
        "fengshui_annual_stars",
        "fengshui_monthly_stars",
        "fengshui_jinsuo",
    )
    assert set(scenario_tools).issubset(discovered_names)

    assess_inputs = augmented_inputs_for("fengshui_assess", all_tool_specs)
    assess_inputs["xuankong"] = {
        "period": {
            "basis": "construction_completion",
            "evidence": "示例：立春后竣工，按竣工事件定运",
            "event_year": 2004,
        }
    }

    batch_outcome = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "subjects": {
                "a": {"birth_year": 1990, "gender": "male"},
                "b": {"birth_year": 1990, "gender": "female"},
            },
            "as_of": e2e_as_of,
            "calls": [
                {"id": "fengshui_directions", "tool": "fengshui_directions"},
                {"id": "fengshui_minggua", "tool": "fengshui_minggua", "subject": "a"},
                {
                    "id": "fengshui_bazhai",
                    "tool": "fengshui_bazhai",
                    "subjects": ["a", "b"],
                    "arguments": {
                        "house": {
                            "object_id": "home",
                            "facing_degrees": 180,
                            "north_reference": "magnetic",
                        }
                    },
                },
                {
                    "id": "fengshui_annual_stars",
                    "tool": "fengshui_annual_stars",
                    "arguments": augmented_inputs_for(
                        "fengshui_annual_stars", all_tool_specs
                    ),
                },
                {
                    "id": "fengshui_monthly_stars",
                    "tool": "fengshui_monthly_stars",
                    "arguments": augmented_inputs_for(
                        "fengshui_monthly_stars", all_tool_specs
                    ),
                },
                {
                    "id": "fengshui_jinsuo",
                    "tool": "fengshui_jinsuo",
                    "arguments": augmented_inputs_for(
                        "fengshui_jinsuo", all_tool_specs
                    ),
                },
            ],
        },
    )
    assert batch_outcome.ok, batch_outcome.payload
    assert batch_outcome.payload["status"] == "ok"
    batch_defaults = {
        item["id"]: item["result"] for item in batch_outcome.payload["results"]
    }
    for item in batch_outcome.payload["results"]:
        _assert_clean_run_metadata(
            item["result"], tool_name=item["id"], as_of=e2e_as_of
        )

    batch_matched_tools = {
        "fengshui_directions",
        "fengshui_annual_stars",
        "fengshui_monthly_stars",
        "fengshui_jinsuo",
    }
    preferred_views: dict[str, str | None] = {
        "fengshui_directions": None,
        "fengshui_minggua": None,
        "fengshui_bazhai": None,
        "fengshui_xuankong_house_chart": "natal_candidates",
        "fengshui_assess": "natal_candidates",
        "fengshui_annual_stars": None,
        "fengshui_monthly_stars": None,
        "fengshui_jinsuo": None,
    }
    for tool_name in scenario_tools:
        inputs = (
            assess_inputs
            if tool_name == "fengshui_assess"
            else augmented_inputs_for(tool_name, all_tool_specs)
        )
        _verify_consultation_drilldown(
            tool_name,
            inputs,
            specs=all_tool_specs,
            as_of=e2e_as_of,
            default_payload=(
                batch_defaults[tool_name] if tool_name in batch_matched_tools else None
            ),
            preferred_view=preferred_views[tool_name],
            projection_fields=["status", "summary"],
        )


# ---------------------------------------------------------------------------
# Scenario 4: Jyotish / Vedic Natal Chart & Vimshottari Dasha Consultation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_4_jyotish_vedic_and_vimshottari_dasha(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    scenario_tools = ("vedic_chart", "vimshottari_dasha")
    discovered_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": list(scenario_tools), "detail": "full"},
    )
    assert discovered_outcome.ok, discovered_outcome.payload
    assert discovered_outcome.payload["matched_count"] == 2

    batch_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "subjects": {"client": DEMO_NATIVE_SUBJECT},
            "context": DEMO_CONSULTATION_CONTEXT,
            "as_of": e2e_as_of,
            "calls": [
                {"id": "vedic_chart", "tool": "vedic_chart", "subject": "client"},
                {
                    "id": "vimshottari_dasha",
                    "tool": "vimshottari_dasha",
                    "subject": "client",
                },
            ],
        },
    )
    assert batch_outcome.ok, batch_outcome.payload
    assert batch_outcome.payload["status"] == "ok"
    batch_defaults = {
        item["id"]: item["result"] for item in batch_outcome.payload["results"]
    }
    _assert_clean_run_metadata(
        batch_defaults["vedic_chart"],
        tool_name="vedic_chart",
        as_of=e2e_as_of,
        expect_omitted=True,
    )
    _assert_clean_run_metadata(
        batch_defaults["vimshottari_dasha"],
        tool_name="vimshottari_dasha",
        as_of=e2e_as_of,
    )

    _verify_consultation_drilldown(
        "vedic_chart",
        augmented_inputs_for("vedic_chart", all_tool_specs),
        specs=all_tool_specs,
        as_of=e2e_as_of,
        preferred_view="strength",
        projection_fields=["summary", "vedic_chart.profile"],
        expect_heavy_omissions=True,
    )
    _verify_consultation_drilldown(
        "vimshottari_dasha",
        augmented_inputs_for("vimshottari_dasha", all_tool_specs),
        specs=all_tool_specs,
        as_of=e2e_as_of,
        preferred_view="stage",
        projection_fields=[
            "summary",
            "vimshottari.current_major",
            "vimshottari.current_sub",
        ],
    )


# ---------------------------------------------------------------------------
# Scenario 5: Western Horary, Election, Natal/Hamburg & Timing/Lifespan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_5_western_horary_election_and_timing_lifespan(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    scenario_tools = (
        "horary_chart",
        "evaluate_election_time",
        "astrology_chart",
        "hamburg_midpoint_chart",
        "western_timing",
        "primary_directions",
        "zodiacal_releasing",
        "persian_directions",
        "numeric_aspect_periods",
    )
    discovered_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": list(scenario_tools), "detail": "full"},
    )
    assert discovered_outcome.ok, discovered_outcome.payload
    assert discovered_outcome.payload["matched_count"] == len(scenario_tools)

    batch_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "subjects": {"native": DEMO_NATIVE_SUBJECT},
            "context": DEMO_CONSULTATION_CONTEXT,
            "defaults": {"house_system": "P", "zodiac_type": "Tropic"},
            "as_of": e2e_as_of,
            "calls": [
                {"id": "horary_chart", "tool": "horary_chart"},
                {"id": "evaluate_election_time", "tool": "evaluate_election_time"},
                {
                    "id": "astrology_chart",
                    "tool": "astrology_chart",
                    "subject": "native",
                },
                {
                    "id": "hamburg_midpoint_chart",
                    "tool": "hamburg_midpoint_chart",
                    "subject": "native",
                },
                {"id": "western_timing", "tool": "western_timing", "subject": "native"},
                {
                    "id": "primary_directions",
                    "tool": "primary_directions",
                    "subject": "native",
                },
                {
                    "id": "zodiacal_releasing",
                    "tool": "zodiacal_releasing",
                    "subject": "native",
                },
                {
                    "id": "persian_directions",
                    "tool": "persian_directions",
                    "subject": "native",
                },
                {
                    "id": "numeric_aspect_periods",
                    "tool": "numeric_aspect_periods",
                    "subject": "native",
                },
            ],
        },
    )
    assert batch_outcome.ok, batch_outcome.payload
    assert batch_outcome.payload["status"] == "ok"
    assert batch_outcome.payload["succeeded"] == len(scenario_tools)
    for item in batch_outcome.payload["results"]:
        _assert_clean_run_metadata(
            item["result"], tool_name=item["id"], as_of=e2e_as_of
        )

    preferred_views: dict[str, str | None] = {
        "horary_chart": "lilly_sign_rays",
        "evaluate_election_time": "calculation_conditions",
        "astrology_chart": "classical_detail",
        "hamburg_midpoint_chart": "geometry",
        "western_timing": "annual",
        "primary_directions": None,
        "zodiacal_releasing": None,
        "persian_directions": None,
        "numeric_aspect_periods": None,
    }
    projection_map: dict[str, list[str]] = {
        "horary_chart": ["summary", "horary_chart.significators"],
        "evaluate_election_time": ["summary", "election.factors"],
        "astrology_chart": ["summary", "planets"],
        "hamburg_midpoint_chart": ["chart_profile", "midpoint_analysis"],
        "western_timing": ["summary", "time_lords"],
        "primary_directions": ["summary", "primary_directions"],
        "zodiacal_releasing": ["summary", "zodiacal_releasing"],
        "persian_directions": ["summary", "persian_directions"],
        "numeric_aspect_periods": ["summary", "numeric_aspect_periods"],
    }
    heavy_tools = {
        "horary_chart",
        "astrology_chart",
        "hamburg_midpoint_chart",
        "western_timing",
        "primary_directions",
        "zodiacal_releasing",
    }

    for tool_name in scenario_tools:
        _verify_consultation_drilldown(
            tool_name,
            augmented_inputs_for(tool_name, all_tool_specs),
            specs=all_tool_specs,
            as_of=e2e_as_of,
            preferred_view=preferred_views[tool_name],
            projection_fields=projection_map[tool_name],
            expect_heavy_omissions=tool_name in heavy_tools,
        )


# ---------------------------------------------------------------------------
# Scenario 6: Human Design, Guolao & Reference / Psychometrics Consultation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_6_human_design_guolao_and_reference_psychometrics(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    scenario_tools = (
        "human_design",
        "guolao_chart",
        "knowledge_catalog",
        "knowledge_read",
        "ipip_big_five",
    )
    discover_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tools": list(scenario_tools), "detail": "full"},
    )
    assert discover_outcome.ok, discover_outcome.payload
    assert discover_outcome.payload["matched_count"] == len(scenario_tools)

    # Step 1 of psychometrics workflow: list_items -> confirm 50 items before scoring
    list_res = call_python_run(
        "ipip_big_five",
        EXTRA_DOMAIN_INPUTS["ipip_big_five_list"],
        as_of=e2e_as_of,
    )
    assert list_res.ok, list_res.payload
    assert list_res.payload.get("item_count") == 50
    assert len(list_res.payload.get("items", [])) == 50
    _assert_clean_run_metadata(
        list_res.payload, tool_name="ipip_big_five", as_of=e2e_as_of
    )

    tool_inputs: dict[str, dict[str, Any]] = {
        "human_design": augmented_inputs_for("human_design", all_tool_specs),
        "guolao_chart": augmented_inputs_for("guolao_chart", all_tool_specs),
        "knowledge_catalog": dict(AUGMENTED_TOOL_INPUTS["knowledge_catalog"]),
        "knowledge_read": dict(AUGMENTED_TOOL_INPUTS["knowledge_read"]),
        "ipip_big_five": dict(AUGMENTED_TOOL_INPUTS["ipip_big_five"]),
    }
    preferred_views: dict[str, str | None] = {
        "human_design": "profile",
        "guolao_chart": "classical",
        "knowledge_catalog": "sources",
        "knowledge_read": "human_design_line_reference",
        "ipip_big_five": None,
    }
    projection_map: dict[str, list[str]] = {
        "human_design": ["summary", "profile", "incarnation_cross"],
        "guolao_chart": ["chart_profile", "guolao.life_palace"],
        "knowledge_catalog": ["bundle_version", "domains"],
        "knowledge_read": ["domain", "category", "key", "title", "lines"],
        "ipip_big_five": ["scale_id", "mode", "status", "summary", "domains"],
    }
    heavy_tools = {"human_design", "guolao_chart"}

    for tool_name in scenario_tools:
        _verify_consultation_drilldown(
            tool_name,
            tool_inputs[tool_name],
            specs=all_tool_specs,
            as_of=e2e_as_of,
            preferred_view=preferred_views[tool_name],
            projection_fields=projection_map[tool_name],
            expect_heavy_omissions=tool_name in heavy_tools,
        )
