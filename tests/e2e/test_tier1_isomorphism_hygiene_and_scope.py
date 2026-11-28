"""Tier 1b opaque-box E2E tests for Plan A R2, R3, and R4 contracts.

Covers:
- R2 legacy bloat & discovery artifact removal across all 91 tools
- R2 & R4 strict isomorphism and `omitted_fields` consistency across all 91 tools
  plus supplemental domain modes and C-class tools
- R3 scope-to-input parameterization and explicit `*_total_count` invariants
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import (
    AUGMENTED_TOOL_INPUTS,
    EXTRA_DOMAIN_INPUTS,
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_cli,
    call_mcp_tool,
    call_python_run,
    call_rest_get,
    find_bloat_keys,
    get_all_full_specs,
    has_dotted_path,
    strip_run_metadata,
)

EXPECTED_TOOL_COUNT = 91
LEGACY_DISCOVERY_KEYS: frozenset[str] = frozenset(
    {"compact_fields", "compact_view", "detail_view"}
)
FORBIDDEN_SHORT_ALIASES: frozenset[str] = frozenset(
    {"deg", "dig", "lon", "rx", "ok", "p", "m", "f"}
)

ALL_TOOL_NAMES: tuple[str, ...] = tuple(sorted(get_all_full_specs()))

C_CLASS_TOOLS: tuple[str, ...] = (
    "ziwei_birth_chart",
    "ziwei_timing",
    "vedic_chart",
    "vimshottari_dasha",
    "human_design",
    "guolao_chart",
    "fengshui_annual_stars",
    "fengshui_assess",
    "fengshui_bazhai",
    "fengshui_directions",
    "fengshui_jinsuo",
    "fengshui_minggua",
    "fengshui_monthly_stars",
    "fengshui_xuankong_house_chart",
    "horary_chart",
    "astrology_chart",
    "hamburg_midpoint_chart",
    "relationship_chart",
    "western_timing",
    "primary_directions",
    "zodiacal_releasing",
    "decennials",
    "bazi_timing",
    "qimen",
    "knowledge_catalog",
    "solar_terms_for_year",
)

SUPPLEMENTAL_MODES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("ipip_big_five_score", "ipip_big_five", AUGMENTED_TOOL_INPUTS["ipip_big_five"]),
    (
        "ipip_big_five_list",
        "ipip_big_five",
        EXTRA_DOMAIN_INPUTS["ipip_big_five_list"],
    ),
    (
        "knowledge_read_human_design",
        "knowledge_read",
        AUGMENTED_TOOL_INPUTS["knowledge_read"],
    ),
    (
        "knowledge_read_numerology",
        "knowledge_read",
        EXTRA_DOMAIN_INPUTS["knowledge_read_numerology"],
    ),
    (
        "knowledge_catalog_all",
        "knowledge_catalog",
        AUGMENTED_TOOL_INPUTS["knowledge_catalog"],
    ),
)

WESTERN_TIMING_TOOLS: tuple[str, ...] = (
    "western_timing",
    "primary_directions",
    "primary_directions_chart",
    "transit_chart",
    "solar_arc",
    "profection",
    "chart_for_year",
    "decennials",
)


def _iter_dict_nodes_with_ancestors(
    obj: Any,
    prefix: str = "",
    ancestors: tuple[tuple[str, dict[str, Any]], ...] = (),
) -> Iterator[tuple[str, dict[str, Any], tuple[tuple[str, dict[str, Any]], ...]]]:
    if isinstance(obj, dict):
        yield prefix, obj, ancestors
        next_ancestors = ((prefix, obj), *ancestors)
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _iter_dict_nodes_with_ancestors(value, child, next_ancestors)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _iter_dict_nodes_with_ancestors(
                item, f"{prefix}[{index}]", ancestors
            )


def _find_short_alias_keys(obj: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = str(key)
            path = f"{prefix}.{key_str}" if prefix else key_str
            if key_str in FORBIDDEN_SHORT_ALIASES:
                hits.append(path)
            hits.extend(_find_short_alias_keys(value, path))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            hits.extend(_find_short_alias_keys(item, f"{prefix}[{index}]"))
    return hits


def _assert_default_vs_full_invariants(
    tool_name: str,
    default_payload: dict[str, Any],
    full_payload: dict[str, Any],
) -> None:
    assert find_bloat_keys(default_payload) == [], (
        f"{tool_name} default payload leaked bloat keys: "
        f"{find_bloat_keys(default_payload)}"
    )
    assert find_bloat_keys(full_payload) == [], (
        f"{tool_name} include=['*'] payload leaked bloat keys: "
        f"{find_bloat_keys(full_payload)}"
    )

    default_business = strip_run_metadata(default_payload)
    full_business = strip_run_metadata(full_payload)
    assert_isomorphic_subset(default_business, full_business)

    full_omitted = full_payload.get("run_metadata", {}).get("omitted_fields")
    assert (
        not full_omitted
    ), f"{tool_name} include=['*'] must not report omitted_fields: {full_omitted!r}"

    default_omitted = default_payload.get("run_metadata", {}).get("omitted_fields")
    if default_business != full_business:
        assert isinstance(default_omitted, list) and len(default_omitted) > 0, (
            f"{tool_name}: default payload differs from include=['*'] without "
            f"declaring non-empty run_metadata.omitted_fields (got {default_omitted!r})"
        )
    if default_omitted is not None:
        assert isinstance(default_omitted, list)
        for omitted_path in default_omitted:
            assert isinstance(omitted_path, str) and omitted_path
            assert not has_dotted_path(default_business, omitted_path), (
                f"{tool_name}: omitted path {omitted_path!r} still present in "
                "default payload"
            )
            assert has_dotted_path(full_business, omitted_path), (
                f"{tool_name}: omitted path {omitted_path!r} missing from "
                "include=['*'] payload"
            )


HORIZON_AND_ORB_PARAMS: frozenset[str] = frozenset(
    {
        "max_age_years",
        "pd_max_age_years",
        "pd_nearby_years",
        "orb",
        "orb_limit",
        "scan_days",
        "scan_months",
        "search_window_hours",
        "end_year",
    }
)


def _discover_limit_params(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return list-cap/truncation parameters, excluding horizon/orb scope filters."""
    props = spec.get("input_schema", {}).get("properties", {})
    found: dict[str, dict[str, Any]] = {}
    for name, schema in props.items():
        if name in HORIZON_AND_ORB_PARAMS:
            continue
        if (
            name.startswith("max_")
            or name.endswith("_limit")
            or name == "limit"
            or name == "pd_window_size"
        ):
            found[name] = schema
    return found


def _assert_total_count_invariants(
    tool_name: str,
    payload: dict[str, Any],
    *,
    expect_equal_when_no_limit: bool,
    min_total_count_keys: int = 0,
) -> int:
    found_count = 0
    for path, node, ancestors in _iter_dict_nodes_with_ancestors(
        strip_run_metadata(payload)
    ):
        for key, value in node.items():
            if key.endswith("_total_count"):
                stem = key[: -len("_total_count")]
            elif key.startswith("total_") and key.endswith("_count"):
                stem = key[len("total_") : -len("_count")]
            else:
                continue
            found_count += 1
            count_loc = f"{path}.{key}" if path else key
            assert (
                isinstance(value, int) and value >= 0
            ), f"{tool_name} {count_loc} must be non-negative int, got {value!r}"
            candidates = (
                stem,
                f"{stem}_contacts",
                f"{stem}_hits",
                f"{stem}_intervals",
                f"{stem}_windows",
                f"{stem}_aspects",
                f"{stem}_activations",
            )
            matched: list[tuple[str, str, list[Any]]] = [
                (path, cand, node[cand])
                for cand in candidates
                if isinstance(node.get(cand), list)
            ]
            if not matched:
                for anc_path, anc_node in ancestors:
                    anc_matched = [
                        (anc_path, cand, anc_node[cand])
                        for cand in candidates
                        if isinstance(anc_node.get(cand), list)
                    ]
                    if anc_matched:
                        matched = anc_matched
                        break
            assert matched, (
                f"{tool_name} emitted {count_loc}={value} without matching list "
                f"field in {sorted(node)} or ancestors "
                f"{[anc_path or '<root>' for anc_path, _ in ancestors]}"
            )
            for list_path, cand, items in matched:
                list_loc = f"{list_path}.{cand}" if list_path else cand
                assert (
                    len(items) <= value
                ), f"{tool_name} {list_loc} len={len(items)} exceeds {count_loc}={value}"
                if expect_equal_when_no_limit:
                    assert len(items) == value, (
                        f"{tool_name} {list_loc} silently truncated "
                        f"({len(items)} != {value}) without explicit limit parameter"
                    )
    assert found_count >= min_total_count_keys, (
        f"{tool_name}: expected at least {min_total_count_keys} total_count keys, "
        f"found {found_count}"
    )
    return found_count


def _schema_has_default_cap(schema: dict[str, Any]) -> bool:
    default = schema.get("default")
    return isinstance(default, int) and not isinstance(default, bool)


# ---------------------------------------------------------------------------
# R2: Catalog completeness, schema bloat removal & discovery hygiene
# ---------------------------------------------------------------------------


def test_catalog_has_91_tools_and_output_schemas_have_no_bloat(
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    import fatebridge

    assert len(all_tool_specs) == EXPECTED_TOOL_COUNT
    summary = fatebridge.discover(detail="summary")
    assert summary["counts"]["total"] == EXPECTED_TOOL_COUNT

    for tool_name, spec in sorted(all_tool_specs.items()):
        assert not (LEGACY_DISCOVERY_KEYS & set(spec)), (
            f"{tool_name} full spec still exposes legacy keys: "
            f"{sorted(LEGACY_DISCOVERY_KEYS & set(spec))}"
        )
        output_schema = spec.get("output_schema")
        assert isinstance(
            output_schema, dict
        ), f"{tool_name} missing output_schema in full discovery"
        bloat_hits = find_bloat_keys(output_schema)
        assert (
            bloat_hits == []
        ), f"{tool_name} output_schema still declares legacy bloat keys: {bloat_hits}"


@pytest.mark.asyncio
async def test_discovery_brief_and_full_remove_legacy_view_and_compact_keys(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    import fatebridge

    py_brief = fatebridge.discover(detail="brief")
    brief_tools = py_brief.get("tools", [])
    assert len(brief_tools) == EXPECTED_TOOL_COUNT
    for record in brief_tools:
        assert not (LEGACY_DISCOVERY_KEYS & set(record)), (
            f"Python brief discovery for {record.get('tool')!r} still exposes "
            f"{sorted(LEGACY_DISCOVERY_KEYS & set(record))}"
        )

    mcp_brief = await call_mcp_tool(mcp_client, "discover_tools", {"detail": "brief"})
    assert mcp_brief.ok, mcp_brief.payload
    for record in mcp_brief.payload.get("tools", []):
        assert not (LEGACY_DISCOVERY_KEYS & set(record))

    rest_brief = call_rest_get(rest_client, "/api/tools", params={"detail": "brief"})
    assert rest_brief.ok, rest_brief.payload
    for record in rest_brief.payload.get("tools", []):
        assert not (LEGACY_DISCOVERY_KEYS & set(record))

    families = sorted(fatebridge.discover(detail="summary")["families"])
    for family in families:
        py_full = fatebridge.discover(
            family=family, detail="full", include_output_schema=True
        )
        for record in py_full.get("tools", []):
            assert not (LEGACY_DISCOVERY_KEYS & set(record))
            assert find_bloat_keys(record.get("output_schema")) == []

    for sample_tool in ("bazi_overview", "astrology_chart", "ziwei_birth_chart"):
        assert sample_tool in all_tool_specs
        mcp_full = await call_mcp_tool(
            mcp_client,
            "discover_tools",
            {"tool": sample_tool, "detail": "full", "include_output_schema": True},
        )
        assert mcp_full.ok, mcp_full.payload
        assert not (LEGACY_DISCOVERY_KEYS & set(mcp_full.payload))
        assert find_bloat_keys(mcp_full.payload.get("output_schema")) == []

        cli_brief = call_cli(["discover", sample_tool, "--detail", "brief"])
        assert cli_brief.ok, cli_brief.payload
        assert not (LEGACY_DISCOVERY_KEYS & set(cli_brief.payload))

        cli_full = call_cli(["discover", sample_tool, "--detail", "full"])
        assert cli_full.ok, cli_full.payload
        assert not (LEGACY_DISCOVERY_KEYS & set(cli_full.payload))


# ---------------------------------------------------------------------------
# R2 & R4: All-91-tool bloat removal, strict isomorphism & omitted_fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_all_91_tools_hygiene_isomorphism_and_omitted_fields(
    tool_name: str,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    spec = all_tool_specs[tool_name]
    assert find_bloat_keys(spec.get("output_schema")) == []

    example = spec.get("example_input")
    assert isinstance(example, dict), f"{tool_name} missing dict example_input"

    default_out = call_python_run(tool_name, example, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, example, as_of=e2e_as_of, include=["*"])
    assert default_out.ok, f"{tool_name} default failed: {default_out.payload}"
    assert full_out.ok, f"{tool_name} include=['*'] failed: {full_out.payload}"

    _assert_default_vs_full_invariants(tool_name, default_out.payload, full_out.payload)


@pytest.mark.parametrize(
    ("case_id", "tool_name", "payload"),
    SUPPLEMENTAL_MODES,
    ids=[case[0] for case in SUPPLEMENTAL_MODES],
)
def test_supplemental_modes_hygiene_isomorphism_and_omitted_fields(
    case_id: str,
    tool_name: str,
    payload: dict[str, Any],
    e2e_as_of: str,
) -> None:
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok, f"{case_id} default failed: {default_out.payload}"
    assert full_out.ok, f"{case_id} include=['*'] failed: {full_out.payload}"

    _assert_default_vs_full_invariants(case_id, default_out.payload, full_out.payload)


@pytest.mark.parametrize("tool_name", C_CLASS_TOOLS)
def test_c_class_tools_strict_isomorphism_and_no_short_aliases(
    tool_name: str,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    fengshui_in_catalog = {
        name for name in all_tool_specs if name.startswith("fengshui_")
    }
    assert len(fengshui_in_catalog) == 8
    assert fengshui_in_catalog.issubset(set(C_CLASS_TOOLS))

    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok and full_out.ok

    _assert_default_vs_full_invariants(tool_name, default_out.payload, full_out.payload)
    default_alias_hits = _find_short_alias_keys(strip_run_metadata(default_out.payload))
    assert (
        default_alias_hits == []
    ), f"{tool_name} default payload contains short alias keys: {default_alias_hits}"
    full_alias_hits = _find_short_alias_keys(strip_run_metadata(full_out.payload))
    assert (
        full_alias_hits == []
    ), f"{tool_name} include=['*'] payload contains short alias keys: {full_alias_hits}"


def _resolve_schema_branches(node: Any, defs: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    branches: list[dict[str, Any]] = []
    if "$ref" in node and isinstance(node["$ref"], str):
        ref_name = node["$ref"].rsplit("/", 1)[-1]
        if ref_name in defs:
            branches.extend(_resolve_schema_branches(defs[ref_name], defs))
    for key in ("anyOf", "oneOf", "allOf"):
        items = node.get(key)
        if isinstance(items, list):
            for branch in items:
                branches.extend(_resolve_schema_branches(branch, defs))
    if (
        not branches
        or "properties" in node
        or "items" in node
        or "additionalProperties" in node
        or node == {}
    ):
        branches.append(node)
    return branches


def _schema_has_dotted_path(output_schema: dict[str, Any], dotted_path: str) -> bool:
    defs = output_schema.get("$defs")
    defs_dict = defs if isinstance(defs, dict) else {}
    segments = [part for part in dotted_path.split(".") if part]
    if not segments:
        return False

    def walk(node: Any, idx: int) -> bool:
        if idx == len(segments):
            return True
        seg = segments[idx]
        for cand in _resolve_schema_branches(node, defs_dict):
            if cand == {} or (
                cand.get("type") == "object"
                and "properties" not in cand
                and "additionalProperties" not in cand
            ):
                return True
            if seg == "*":
                if "items" in cand and walk(cand["items"], idx + 1):
                    return True
                add_props = cand.get("additionalProperties")
                if isinstance(add_props, dict) and walk(add_props, idx + 1):
                    return True
                if add_props is True:
                    return True
                props = cand.get("properties")
                if isinstance(props, dict) and any(
                    walk(prop_node, idx + 1) for prop_node in props.values()
                ):
                    return True
            else:
                props = cand.get("properties")
                if isinstance(props, dict) and seg in props:
                    if walk(props[seg], idx + 1):
                        return True
                add_props = cand.get("additionalProperties")
                if isinstance(add_props, dict) and walk(add_props, idx + 1):
                    return True
                if add_props is True:
                    return True
        return False

    return walk(output_schema, 0)


def test_all_tools_unconditional_evidence_views_and_meihua_topic_views(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """All unconditional evidence_views, conditional overrides, and Meihua views project cleanly via fields= and include=."""
    for tool_name, spec in sorted(all_tool_specs.items()):
        views = spec.get("evidence_views") or {}
        if not views:
            continue
        example_payload = dict(spec.get("example_input") or {})
        for view_name, view_card in sorted(views.items()):
            fields_list = list(view_card.get("fields") or [])
            assert (
                fields_list
            ), f"{tool_name}.{view_name} published empty fields in evidence_views"
            if "when" in view_card:
                continue
            inc_out = call_python_run(
                tool_name, example_payload, as_of=e2e_as_of, include=[view_name]
            )
            assert (
                inc_out.ok
            ), f"{tool_name} include=[{view_name!r}] failed: {inc_out.payload}"
            fld_out = call_python_run(
                tool_name, example_payload, as_of=e2e_as_of, fields=fields_list
            )
            assert fld_out.ok, (
                f"{tool_name} fields={fields_list!r} for view {view_name!r} failed: "
                f"{fld_out.payload}"
            )

    conditional_overrides: dict[tuple[str, str], dict[str, Any]] = {
        ("hamburg_midpoint_chart", "comparative_geometry"): {
            "birth_time_uncertainty_minutes": 10
        },
        ("hamburg_midpoint_chart", "progression_key"): {
            "analysis_datetime": "2026-10-12T12:00:00+08:00"
        },
        ("hamburg_midpoint_chart", "witte1925_table"): {
            "analysis_datetime": "2026-10-12T12:00:00+08:00"
        },
        ("fengshui_assess", "natal_candidates"): {
            "built_year": 2010,
            "methods": ["bazhai", "jinsuo", "annual_stars", "xuankong_natal"],
        },
        ("fengshui_assess", "natal_patterns"): {
            "built_year": 2010,
            "methods": ["bazhai", "jinsuo", "annual_stars", "xuankong_natal"],
        },
        ("fengshui_xuankong_house_chart", "natal_interpretation"): {
            "interpretation": {"current_period_number": 9},
        },
        ("knowledge_read", "human_design_line_reference"): {
            "domain": "human_design",
            "category": "lines",
            "key": "1.1",
        },
        ("knowledge_read", "numerology_reference"): {
            "domain": "heluo",
            "category": "line_texts",
            "key": "乾為天:1",
        },
    }
    for (tool_name, view_name), override in sorted(conditional_overrides.items()):
        view_card = (all_tool_specs[tool_name].get("evidence_views") or {})[view_name]
        assert (
            "when" in view_card
        ), f"{tool_name}.{view_name} must declare 'when' metadata"
        fields_list = list(view_card["fields"])
        call_payload = {
            **augmented_inputs_for(tool_name, all_tool_specs),
            **override,
        }
        inc_out = call_python_run(
            tool_name, call_payload, as_of=e2e_as_of, include=[view_name]
        )
        assert (
            inc_out.ok
        ), f"{tool_name} conditional include=[{view_name!r}] failed: {inc_out.payload}"
        fld_out = call_python_run(
            tool_name, call_payload, as_of=e2e_as_of, fields=fields_list
        )
        assert fld_out.ok, (
            f"{tool_name} conditional fields={fields_list!r} for view {view_name!r} failed: "
            f"{fld_out.payload}"
        )

    for meihua_tool in ("meihua_time_cast", "meihua_cast"):
        meihua_spec = all_tool_specs[meihua_tool]
        meihua_views = meihua_spec.get("evidence_views") or {}
        assert "chapter_qualitative_motion" not in meihua_views
        guidance_text = str(meihua_spec.get("call_guidance") or "")
        views_text = str(meihua_views)
        for retired_ref in (
            "chapter_qualifications",
            "qi_day_timing_reference",
            "qi_branch_timing_reference",
            "internal_countercontrol",
            "seasonal_qualification",
            "obstruction_timing",
            "postheaven_count_reference",
            "trigram_relation_symbols",
        ):
            assert (
                retired_ref not in guidance_text
            ), f"{meihua_tool} call_guidance still mentions retired {retired_ref!r}"
            assert (
                retired_ref not in views_text
            ), f"{meihua_tool} evidence_views still mentions retired {retired_ref!r}"

        base = dict(meihua_spec.get("example_input") or {})
        trigram_fields = list(meihua_views["trigram_symbols"]["fields"])
        for default_payload in (base, {**base, "interpretation_topic": "general"}):
            inc_default = call_python_run(
                meihua_tool,
                default_payload,
                as_of=e2e_as_of,
                include=["trigram_symbols"],
            )
            fld_default = call_python_run(
                meihua_tool,
                default_payload,
                as_of=e2e_as_of,
                fields=trigram_fields,
            )
            assert (
                inc_default.ok
            ), f"{meihua_tool}(general) include=trigram_symbols: {inc_default.payload}"
            assert (
                fld_default.ok
            ), f"{meihua_tool}(general) fields=trigram_symbols: {fld_default.payload}"

        for topic_name in ("travel", "traveler", "wealth"):
            topic_payload = {**base, "interpretation_topic": topic_name}
            topic_views = ["topic", "topic_details", "trigram_symbols"]
            if topic_name == "wealth":
                topic_views.append("wealth")
            for view_name in topic_views:
                fields_list = list(meihua_views[view_name]["fields"])
                inc_res = call_python_run(
                    meihua_tool, topic_payload, as_of=e2e_as_of, include=[view_name]
                )
                fld_res = call_python_run(
                    meihua_tool, topic_payload, as_of=e2e_as_of, fields=fields_list
                )
                assert (
                    inc_res.ok
                ), f"{meihua_tool}({topic_name}) include={view_name}: {inc_res.payload}"
                assert (
                    fld_res.ok
                ), f"{meihua_tool}({topic_name}) fields={view_name}: {fld_res.payload}"


def test_jyotish_and_horary_guidance_and_docs_reject_stale_paths(
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    """Jyotish and horary call_guidance plus vedic-evidence.md reference live canonical roots only."""
    for jyotish_tool in ("vedic_chart", "vimshottari_dasha"):
        guidance_text = str(all_tool_specs[jyotish_tool].get("call_guidance") or "")
        for retired_ref in (
            "india.",
            "顶层西占字段",
            "topic_evidence.personality",
            "clock_context",
        ):
            assert (
                retired_ref not in guidance_text
            ), f"{jyotish_tool} call_guidance still mentions retired {retired_ref!r}"
        assert "vedic_chart.profile.time_scale_context" in guidance_text

    vedic_views = set(all_tool_specs["vedic_chart"].get("evidence_views") or {})
    assert vedic_views == {"divisions", "natal", "strength"}

    vim_guidance_text = str(
        all_tool_specs["vimshottari_dasha"].get("call_guidance") or ""
    )
    assert "vedic_chart.strengths.sthana_bala" in vim_guidance_text

    horary_guidance_text = str(
        all_tool_specs["horary_chart"].get("call_guidance") or ""
    )
    assert (
        "horary.perfection" not in horary_guidance_text
    ), "horary_chart call_guidance still mentions retired 'horary.perfection'"
    for expected_path in (
        "horary_chart.perfection",
        "horary_chart.moon.motion_basis",
        "horary_chart.rule_profile",
    ):
        assert (
            expected_path in horary_guidance_text
        ), f"horary_chart call_guidance missing canonical path {expected_path!r}"

    vedic_doc = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "interpretation"
        / "shared"
        / "vedic-evidence.md"
    ).read_text(encoding="utf-8")
    for retired_doc_ref in (
        "india.",
        "顶层西占字段",
        "topic_evidence.personality",
        "`career` / `vedic_chart`",
        "`relationship` / `vedic_chart`",
    ):
        assert (
            retired_doc_ref not in vedic_doc
        ), f"vedic-evidence.md still mentions retired {retired_doc_ref!r}"
    for expected_doc_path in (
        "vedic_chart.charts.D1",
        "vedic_chart.strengths.sthana_bala",
        "vedic_chart.profile.time_scale_context",
    ):
        assert (
            expected_doc_path in vedic_doc
        ), f"vedic-evidence.md missing canonical path {expected_doc_path!r}"


def test_all_tools_default_omit_canonical_paths_and_guolao_degree_in_mansion(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """Every tool's default_omit resolves in canonical output or output_schema, and guolao_chart omits degree_in_mansion."""
    for tool_name, spec in sorted(all_tool_specs.items()):
        default_omit = list(spec.get("default_omit") or [])
        if not default_omit:
            continue
        output_schema = spec["output_schema"]
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
        assert full_out.ok, f"{tool_name} include=['*'] failed: {full_out.payload}"
        full_biz = strip_run_metadata(full_out.payload)
        for omit_path in default_omit:
            assert has_dotted_path(full_biz, omit_path) or _schema_has_dotted_path(
                output_schema, omit_path
            ), (
                f"{tool_name}: default_omit path {omit_path!r} matches neither live "
                "include=['*'] output nor public output_schema"
            )

    guolao_spec = all_tool_specs["guolao_chart"]
    guolao_omit = set(guolao_spec.get("default_omit") or [])
    assert "guolao.bodies.*.mansion.right_ascension" in guolao_omit
    assert "guolao.bodies.*.mansion.longitude" in guolao_omit
    assert "guolao.bodies.*.mansion.coordinate" in guolao_omit
    assert "guolao.bodies.*.mansion.degree_in_mansion" in guolao_omit
    assert "guolao.bodies.*.mansion.du_in_mansion" not in guolao_omit
    assert "guolao.bodies.*.mansion.mansion_du_width" not in guolao_omit

    guolao_payload = augmented_inputs_for("guolao_chart", all_tool_specs)
    guolao_default = call_python_run("guolao_chart", guolao_payload, as_of=e2e_as_of)
    guolao_full = call_python_run(
        "guolao_chart", guolao_payload, as_of=e2e_as_of, include=["*"]
    )
    guolao_restored = call_python_run(
        "guolao_chart",
        guolao_payload,
        as_of=e2e_as_of,
        include=["guolao.bodies.*.mansion.degree_in_mansion"],
    )
    assert guolao_default.ok and guolao_full.ok and guolao_restored.ok
    omitted_fields = guolao_default.payload["run_metadata"].get("omitted_fields") or []
    assert "guolao.bodies.*.mansion.degree_in_mansion" in omitted_fields
    assert not has_dotted_path(
        strip_run_metadata(guolao_default.payload),
        "guolao.bodies.*.mansion.degree_in_mansion",
    )
    assert has_dotted_path(
        strip_run_metadata(guolao_full.payload),
        "guolao.bodies.*.mansion.degree_in_mansion",
    )
    assert has_dotted_path(
        strip_run_metadata(guolao_restored.payload),
        "guolao.bodies.*.mansion.degree_in_mansion",
    )
    assert "guolao.bodies.*.mansion.degree_in_mansion" not in (
        guolao_restored.payload["run_metadata"].get("omitted_fields") or []
    )

    for frame_name, coord_path in (
        ("modern_ecliptic", "guolao.bodies.*.mansion.longitude"),
        ("shoushi_ecliptic", "guolao.bodies.*.mansion.coordinate"),
        ("shoushi_equatorial", "guolao.bodies.*.mansion.coordinate"),
    ):
        frame_payload = {**guolao_payload, "mansion_frame": frame_name}
        frame_default = call_python_run("guolao_chart", frame_payload, as_of=e2e_as_of)
        frame_full = call_python_run(
            "guolao_chart", frame_payload, as_of=e2e_as_of, include=["*"]
        )
        frame_restored = call_python_run(
            "guolao_chart",
            frame_payload,
            as_of=e2e_as_of,
            include=[coord_path],
        )
        assert frame_default.ok and frame_full.ok and frame_restored.ok
        frame_omitted = (
            frame_default.payload["run_metadata"].get("omitted_fields") or []
        )
        assert coord_path in frame_omitted
        assert "guolao.bodies.*.mansion.degree_in_mansion" in frame_omitted
        frame_default_biz = strip_run_metadata(frame_default.payload)
        frame_full_biz = strip_run_metadata(frame_full.payload)
        frame_restored_biz = strip_run_metadata(frame_restored.payload)
        assert not has_dotted_path(frame_default_biz, coord_path)
        assert not has_dotted_path(
            frame_default_biz, "guolao.bodies.*.mansion.degree_in_mansion"
        )
        assert has_dotted_path(frame_full_biz, coord_path)
        assert has_dotted_path(
            frame_full_biz, "guolao.bodies.*.mansion.degree_in_mansion"
        )
        assert has_dotted_path(frame_restored_biz, coord_path)
        assert coord_path not in (
            frame_restored.payload["run_metadata"].get("omitted_fields") or []
        )
        for body in frame_default_biz["guolao"]["bodies"]:
            assert set(body["mansion"]) == {"degree_lord", "su28"}


# ---------------------------------------------------------------------------
# R3: Scope-to-Input Parameterization & Explicit `*_total_count`
# ---------------------------------------------------------------------------


def test_r3_astrology_chart_full_aspects_and_optional_limit_param(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "astrology_chart"
    spec = all_tool_specs[tool_name]
    payload = augmented_inputs_for(tool_name, all_tool_specs)

    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok and full_out.ok

    default_aspects = default_out.payload["aspects"]
    full_aspects = full_out.payload["aspects"]
    assert default_aspects == full_aspects
    assert len(default_aspects) > 16 and len(default_aspects) >= 20
    assert default_out.payload["chart_profile"]["aspects_total_count"] == len(
        default_aspects
    )
    _assert_total_count_invariants(
        tool_name,
        default_out.payload,
        expect_equal_when_no_limit=True,
        min_total_count_keys=1,
    )

    limit_params = _discover_limit_params(spec)
    aspect_limit_name = next((name for name in limit_params if "aspect" in name), None)
    assert aspect_limit_name is not None, (
        "astrology_chart must expose an aspect limit parameter (e.g. max_aspects) "
        f"in input_schema, got {sorted(spec.get('input_schema', {}).get('properties', {}))}"
    )
    capped_payload = {**payload, aspect_limit_name: 5}
    capped_out = call_python_run(tool_name, capped_payload, as_of=e2e_as_of)
    assert capped_out.ok, capped_out.payload
    assert len(capped_out.payload["aspects"]) == 5
    assert len(capped_out.payload["aspects"]) < len(full_aspects)
    assert capped_out.payload["chart_profile"]["aspects_total_count"] == len(
        full_aspects
    )
    assert capped_out.payload["chart_profile"]["aspects_returned_count"] == 5
    _assert_total_count_invariants(
        tool_name,
        capped_out.payload,
        expect_equal_when_no_limit=False,
        min_total_count_keys=1,
    )


def test_r3_hamburg_midpoint_chart_dials_and_total_counts(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "hamburg_midpoint_chart"
    spec = all_tool_specs[tool_name]
    base_payload = augmented_inputs_for(tool_name, all_tool_specs)
    limit_params = _discover_limit_params(spec)
    higher_limit_param = next(
        (
            name
            for name in sorted(limit_params)
            if "higher" in name or ("contact" in name and "mixed" not in name)
        ),
        None,
    )
    has_default_cap = any(
        _schema_has_default_cap(schema) for schema in limit_params.values()
    )

    dial90_payload = {**base_payload, "dial_degrees": "90"}
    dial22_payload = {**base_payload, "dial_degrees": "22.5"}

    res_90 = call_python_run(tool_name, dial90_payload, as_of=e2e_as_of)
    res_90_full = call_python_run(
        tool_name, dial90_payload, as_of=e2e_as_of, include=["*"]
    )
    res_22 = call_python_run(tool_name, dial22_payload, as_of=e2e_as_of)
    res_22_full = call_python_run(
        tool_name, dial22_payload, as_of=e2e_as_of, include=["*"]
    )
    assert res_90.ok and res_90_full.ok and res_22.ok and res_22_full.ok
    _assert_default_vs_full_invariants(tool_name, res_90.payload, res_90_full.payload)
    _assert_default_vs_full_invariants(tool_name, res_22.payload, res_22_full.payload)

    dials_90 = res_90_full.payload["midpoint_analysis"]["dials"]
    dials_22 = res_22_full.payload["midpoint_analysis"]["dials"]
    assert set(dials_90) == {"90", "45"}
    assert set(dials_22) == {"90", "45", "22.5"}

    for dial_key in ("90", "45"):
        assert "three_factor_total_count" in dials_90[dial_key]
        assert "four_factor_total_count" in dials_90[dial_key]
        assert (
            dials_90[dial_key]["three_factor_total_count"]
            == dials_22[dial_key]["three_factor_total_count"]
        )
        assert (
            dials_90[dial_key]["four_factor_total_count"]
            == dials_22[dial_key]["four_factor_total_count"]
        )

    for dials in (dials_90, dials_22):
        for dial_key, dial_data in dials.items():
            assert "three_factor_total_count" in dial_data
            assert "four_factor_total_count" in dial_data
            three_contacts = dial_data["three_factor_contacts"]
            four_contacts = dial_data["four_factor_contacts"]
            three_total = dial_data["three_factor_total_count"]
            four_total = dial_data["four_factor_total_count"]
            assert isinstance(three_total, int) and three_total > 0
            assert isinstance(four_total, int) and four_total > 0
            assert len(three_contacts) <= three_total
            assert len(four_contacts) <= four_total
            if len(three_contacts) < three_total or len(four_contacts) < four_total:
                assert higher_limit_param is not None, (
                    f"dial {dial_key} truncated without higher-factor limit parameter "
                    f"in schema: {sorted(limit_params)}"
                )
            if not has_default_cap:
                assert len(three_contacts) == three_total, (
                    f"dial {dial_key} three_factor_contacts silently sliced "
                    f"({len(three_contacts)} != {three_total})"
                )
                assert len(four_contacts) == four_total, (
                    f"dial {dial_key} four_factor_contacts silently sliced "
                    f"({len(four_contacts)} != {four_total})"
                )

    if higher_limit_param is not None:
        low_res = call_python_run(
            tool_name,
            {**dial22_payload, higher_limit_param: 3},
            as_of=e2e_as_of,
            include=["*"],
        )
        high_res = call_python_run(
            tool_name,
            {**dial22_payload, higher_limit_param: 15},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert low_res.ok and high_res.ok
        _assert_total_count_invariants(
            tool_name,
            low_res.payload,
            expect_equal_when_no_limit=False,
            min_total_count_keys=6,
        )
        _assert_total_count_invariants(
            tool_name,
            high_res.payload,
            expect_equal_when_no_limit=False,
            min_total_count_keys=6,
        )
        low_22 = low_res.payload["midpoint_analysis"]["dials"]["22.5"]
        high_22 = high_res.payload["midpoint_analysis"]["dials"]["22.5"]
        assert low_22["three_factor_total_count"] == high_22["three_factor_total_count"]
        assert low_22["four_factor_total_count"] == high_22["four_factor_total_count"]
        assert len(low_22["three_factor_contacts"]) == 3
        assert len(high_22["three_factor_contacts"]) == 15
        assert len(low_22["four_factor_contacts"]) == 3
        assert len(high_22["four_factor_contacts"]) == 15

    for param_name in sorted(limit_params):
        if param_name == higher_limit_param:
            continue
        low_res = call_python_run(
            tool_name,
            {**dial22_payload, param_name: 1},
            as_of=e2e_as_of,
            include=["*"],
        )
        high_res = call_python_run(
            tool_name,
            {**dial22_payload, param_name: 5},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert low_res.ok and high_res.ok
        _assert_total_count_invariants(
            tool_name,
            low_res.payload,
            expect_equal_when_no_limit=False,
            min_total_count_keys=6,
        )
        _assert_total_count_invariants(
            tool_name,
            high_res.payload,
            expect_equal_when_no_limit=False,
            min_total_count_keys=6,
        )


def _western_timing_min_total_counts(tool_name: str) -> int:
    return {
        "western_timing": 9,
        "primary_directions": 5,
        "primary_directions_chart": 2,
        "transit_chart": 1,
        "solar_arc": 1,
        "chart_for_year": 1,
        "profection": 0,
        "decennials": 0,
    }[tool_name]


def _extract_primary_directions_node(
    tool_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    if tool_name == "western_timing":
        node = payload["directions"]["primary_directions"]
        assert isinstance(node, dict)
        return node
    node = payload[tool_name]
    assert isinstance(node, dict)
    return node


def _extract_hits_container(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "western_timing":
        node = payload["transits"]["current_transit"]
        assert isinstance(node, dict)
        return node
    node = payload[tool_name]
    assert isinstance(node, dict)
    return node


def test_r3_western_timing_suite_scope_and_no_silent_truncation(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name in WESTERN_TIMING_TOOLS:
        spec = all_tool_specs[tool_name]
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
        full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
        assert default_out.ok, f"{tool_name} default failed: {default_out.payload}"
        assert full_out.ok, f"{tool_name} include=['*'] failed: {full_out.payload}"
        _assert_default_vs_full_invariants(
            tool_name, default_out.payload, full_out.payload
        )

        limit_params = _discover_limit_params(spec)
        has_default_cap = any(
            _schema_has_default_cap(schema) for schema in limit_params.values()
        )
        _assert_total_count_invariants(
            tool_name,
            full_out.payload,
            expect_equal_when_no_limit=not has_default_cap,
            min_total_count_keys=_western_timing_min_total_counts(tool_name),
        )

        if tool_name == "decennials":
            assert len(full_out.payload["decennials"]["timeline"]) == 7

        if "max_hits" in limit_params:
            wide_base = {**payload, "orb_limit": 15.0}
            small_hits_res = call_python_run(
                tool_name,
                {**wide_base, "max_hits": 2},
                as_of=e2e_as_of,
                include=["*"],
            )
            large_hits_res = call_python_run(
                tool_name,
                {**wide_base, "max_hits": 10},
                as_of=e2e_as_of,
                include=["*"],
            )
            unlimited_hits_res = call_python_run(
                tool_name,
                {**wide_base, "max_hits": None},
                as_of=e2e_as_of,
                include=["*"],
            )
            assert small_hits_res.ok and large_hits_res.ok and unlimited_hits_res.ok
            small_box = _extract_hits_container(tool_name, small_hits_res.payload)
            large_box = _extract_hits_container(tool_name, large_hits_res.payload)
            unlim_box = _extract_hits_container(tool_name, unlimited_hits_res.payload)
            assert len(small_box["hits"]) == 2
            assert len(large_box["hits"]) == 10
            assert len(unlim_box["hits"]) > 10
            assert unlim_box["hits_total_count"] == len(unlim_box["hits"])
            assert small_box["hits_total_count"] == unlim_box["hits_total_count"]
            assert large_box["hits_total_count"] == unlim_box["hits_total_count"]

        if "pd_window_size" in limit_params:
            small_ws = call_python_run(
                tool_name,
                {**payload, "pd_window_size": 2},
                as_of=e2e_as_of,
                include=["*"],
            )
            large_ws = call_python_run(
                tool_name,
                {**payload, "pd_window_size": 10},
                as_of=e2e_as_of,
                include=["*"],
            )
            assert small_ws.ok and large_ws.ok
            if tool_name == "primary_directions_chart":
                small_pdc = small_ws.payload[tool_name]
                large_pdc = large_ws.payload[tool_name]
                assert len(small_pdc["hits"]) == 2
                assert len(large_pdc["hits"]) == 10
            else:
                small_pd = _extract_primary_directions_node(tool_name, small_ws.payload)
                large_pd = _extract_primary_directions_node(tool_name, large_ws.payload)
                assert len(small_pd["current_window"]) == 2
                assert len(large_pd["current_window"]) == 10
                assert (
                    small_pd["current_window_total_count"]
                    == large_pd["current_window_total_count"]
                )

        if (
            "pd_timeline_limit" in limit_params
            and tool_name != "primary_directions_chart"
        ):
            props = spec.get("input_schema", {}).get("properties", {})
            if "include_full_timelines" in props:
                tl_base = {
                    **payload,
                    "include_full_timelines": False,
                    "pd_nearby_years": 50.0,
                }
                small_tl = call_python_run(
                    tool_name,
                    {**tl_base, "pd_timeline_limit": 2},
                    as_of=e2e_as_of,
                    include=["*"],
                )
                large_tl = call_python_run(
                    tool_name,
                    {**tl_base, "pd_timeline_limit": 10},
                    as_of=e2e_as_of,
                    include=["*"],
                )
                assert small_tl.ok and large_tl.ok
                small_pd = _extract_primary_directions_node(tool_name, small_tl.payload)
                large_pd = _extract_primary_directions_node(tool_name, large_tl.payload)
                assert len(small_pd["timeline"]) == 2
                assert len(large_pd["timeline"]) == 10
                assert (
                    small_pd["total_timeline_count"] == large_pd["total_timeline_count"]
                )
            else:
                standalone_pd = _extract_primary_directions_node(
                    tool_name, full_out.payload
                )
                assert (
                    len(standalone_pd["timeline"])
                    == standalone_pd["total_timeline_count"]
                )

    transit_payload = augmented_inputs_for("transit_chart", all_tool_specs)
    transit_1d = call_python_run(
        "transit_chart",
        {**transit_payload, "scan_days": 1},
        as_of=e2e_as_of,
        include=["*"],
    )
    transit_30d = call_python_run(
        "transit_chart",
        {**transit_payload, "scan_days": 30},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert transit_1d.ok and transit_30d.ok
    tl_1 = transit_1d.payload["transit_chart"]["transit_timeline"]
    tl_30 = transit_30d.payload["transit_chart"]["transit_timeline"]
    assert isinstance(tl_1, list) and len(tl_1) == 1
    assert isinstance(tl_30, list) and len(tl_30) == 30
    assert len(tl_1) < len(tl_30)
    assert strip_run_metadata(transit_1d.payload) != strip_run_metadata(
        transit_30d.payload
    )
    _assert_total_count_invariants(
        "transit_chart",
        transit_30d.payload,
        expect_equal_when_no_limit=True,
        min_total_count_keys=1,
    )

    transit_wide = call_python_run(
        "transit_chart",
        {**transit_payload, "orb_limit": 15.0, "max_hits": None},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert transit_wide.ok
    wide_tc = transit_wide.payload["transit_chart"]
    assert len(wide_tc["hits"]) > 24
    assert wide_tc["hits_total_count"] == len(wide_tc["hits"])

    wt_payload = augmented_inputs_for("western_timing", all_tool_specs)
    wt_compact_tl = call_python_run(
        "western_timing",
        {**wt_payload, "include_full_timelines": False},
        as_of=e2e_as_of,
        include=["*"],
    )
    wt_full_tl = call_python_run(
        "western_timing",
        {**wt_payload, "include_full_timelines": True},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert wt_compact_tl.ok and wt_full_tl.ok
    assert wt_full_tl.payload != wt_compact_tl.payload
    compact_pd = wt_compact_tl.payload["directions"]["primary_directions"]
    full_pd = wt_full_tl.payload["directions"]["primary_directions"]
    assert len(full_pd["timeline"]) > len(compact_pd["timeline"])
    assert len(full_pd["timeline"]) == full_pd["total_timeline_count"]


def test_r3_western_lifespan_scope_params_and_total_counts(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    persian_payload = augmented_inputs_for("persian_directions", all_tool_specs)
    persian_spec = all_tool_specs["persian_directions"]
    persian_limits = _discover_limit_params(persian_spec)
    assert "max_age_years" not in persian_limits
    p10 = call_python_run(
        "persian_directions",
        {**persian_payload, "max_age_years": 10.0},
        as_of=e2e_as_of,
        include=["*"],
    )
    p90 = call_python_run(
        "persian_directions",
        {**persian_payload, "max_age_years": 90.0},
        as_of=e2e_as_of,
        include=["*"],
    )
    p200 = call_python_run(
        "persian_directions",
        {**persian_payload, "max_age_years": 200.0},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert p10.ok and p90.ok and p200.ok
    hits_10 = p10.payload["persian_directions"]["hits"]
    hits_90 = p90.payload["persian_directions"]["hits"]
    pd_200 = p200.payload["persian_directions"]
    hits_200 = pd_200["hits"]
    assert len(hits_10) > 0
    assert len(hits_10) < len(hits_90)
    for hit in hits_10:
        age_val = hit.get("age", hit.get("age_years"))
        assert age_val is not None, f"persian_directions hit missing age: {hit!r}"
        assert age_val <= 10.0
    total_hits_200 = pd_200.get("hits_total_count", pd_200.get("total_hit_count"))
    assert (isinstance(total_hits_200, int) and total_hits_200 >= len(hits_200)) or len(
        hits_200
    ) > 120, (
        "persian_directions max_age_years=200.0 silently capped at 120 without "
        "hits_total_count/total_hit_count"
    )
    if "limit" in persian_limits:
        p_lim10 = call_python_run(
            "persian_directions",
            {**persian_payload, "max_age_years": 200.0, "limit": 10},
            as_of=e2e_as_of,
            include=["*"],
        )
        p_unlim = call_python_run(
            "persian_directions",
            {**persian_payload, "max_age_years": 200.0, "limit": None},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert p_lim10.ok and p_unlim.ok
        assert len(p_lim10.payload["persian_directions"]["hits"]) == 10
        assert len(p_unlim.payload["persian_directions"]["hits"]) > 120
    _assert_total_count_invariants(
        "persian_directions",
        p200.payload,
        expect_equal_when_no_limit=not any(
            _schema_has_default_cap(s) for s in persian_limits.values()
        ),
    )

    for tool_name, key_field in (
        ("planetary_arc_directions", "planetary_arc"),
        ("sidereal_progressions", "sidereal_progressions"),
    ):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        spec = all_tool_specs[tool_name]
        limits = _discover_limit_params(spec)
        narrow = call_python_run(
            tool_name, {**payload, "orb": 0.0}, as_of=e2e_as_of, include=["*"]
        )
        wide = call_python_run(
            tool_name, {**payload, "orb": 15.0}, as_of=e2e_as_of, include=["*"]
        )
        assert narrow.ok and wide.ok
        narrow_hits = narrow.payload[key_field]["hits"]
        wide_box = wide.payload[key_field]
        wide_hits = wide_box["hits"]
        assert len(narrow_hits) < len(wide_hits)
        total_wide = wide_box.get("hits_total_count", wide_box.get("total_hit_count"))
        assert len(wide_hits) > 12 or (
            isinstance(total_wide, int) and total_wide > len(wide_hits)
        ), f"{tool_name} orb=15.0 appears silently capped at {len(wide_hits)}"
        if "max_hits" in limits:
            capped = call_python_run(
                tool_name,
                {**payload, "orb": 15.0, "max_hits": 3},
                as_of=e2e_as_of,
                include=["*"],
            )
            assert capped.ok, capped.payload
            capped_hits = capped.payload[key_field]["hits"]
            assert len(capped_hits) == 3 < len(wide_hits)
        _assert_total_count_invariants(
            tool_name,
            wide.payload,
            expect_equal_when_no_limit=not any(
                _schema_has_default_cap(s) for s in limits.values()
            ),
        )

    nap_payload = augmented_inputs_for("numeric_aspect_periods", all_tool_specs)
    nap_spec = all_tool_specs["numeric_aspect_periods"]
    nap_limits = _discover_limit_params(nap_spec)
    assert (
        "max_age_years" not in nap_limits
    ), "max_age_years is a horizon filter, not a list-cap parameter"
    nap_10 = call_python_run(
        "numeric_aspect_periods",
        {**nap_payload, "max_age_years": 10},
        as_of=e2e_as_of,
        include=["*"],
    )
    nap_120 = call_python_run(
        "numeric_aspect_periods",
        {**nap_payload, "max_age_years": 120},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert nap_10.ok and nap_120.ok
    acts_10 = nap_10.payload["numeric_aspect_periods"]["activations"]
    acts_120 = nap_120.payload["numeric_aspect_periods"]["activations"]
    assert 0 < len(acts_10) < len(acts_120)
    assert len(acts_120) > 10
    _assert_total_count_invariants(
        "numeric_aspect_periods",
        nap_120.payload,
        expect_equal_when_no_limit=True,
    )


def test_r3_evaluate_election_time_candidate_windows_and_total_count(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "evaluate_election_time"
    spec = all_tool_specs[tool_name]
    payload = {
        **augmented_inputs_for(tool_name, all_tool_specs),
        "search_window_hours": 24,
    }
    res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert res.ok, res.payload

    election = res.payload["election"]
    windows = election["candidate_windows"]
    assert isinstance(windows, list) and len(windows) > 0

    limit_params = _discover_limit_params(spec)
    window_limit_param = next(
        (name for name in limit_params if "window" in name or name == "limit"),
        None,
    )
    total_count = election.get("candidate_windows_total_count")
    assert (
        isinstance(total_count, int) and total_count >= len(windows) and total_count > 5
    ) or len(windows) > 5, (
        "evaluate_election_time with search_window_hours=24 must expose "
        "candidate_windows_total_count > 5 or return > 5 windows without silent slicing"
    )
    if total_count is not None and window_limit_param is None:
        assert len(windows) == total_count

    if window_limit_param is not None:
        low_res = call_python_run(
            tool_name,
            {**payload, window_limit_param: 2},
            as_of=e2e_as_of,
            include=["*"],
        )
        high_res = call_python_run(
            tool_name,
            {**payload, window_limit_param: 8},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert low_res.ok and high_res.ok
        low_el = low_res.payload["election"]
        high_el = high_res.payload["election"]
        assert len(low_el["candidate_windows"]) == 2
        assert len(high_el["candidate_windows"]) == 8
        assert (
            low_el["candidate_windows_total_count"]
            == high_el["candidate_windows_total_count"]
        )
        assert low_el["candidate_windows_total_count"] > 8


def test_r3_knowledge_catalog_keys_complete_and_sample_limit(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "knowledge_catalog"
    spec = all_tool_specs[tool_name]
    res = call_python_run(tool_name, {}, as_of=e2e_as_of, include=["*"])
    assert res.ok, res.payload

    domains = res.payload["domains"]
    assert isinstance(domains, list) and len(domains) > 0
    saw_partial = False
    for domain_entry in domains:
        for category in domain_entry["categories"]:
            count = category["count"]
            assert isinstance(count, int) and count >= 0
            sample = (
                category["keys_sample"]
                if "keys_sample" in category
                else category["keys"]
            )
            assert isinstance(sample, list)
            assert "keys_complete" in category and isinstance(
                category["keys_complete"], bool
            ), (
                f"{domain_entry['domain']}.{category['name']} missing boolean "
                "keys_complete"
            )
            expected_complete = len(sample) == count
            if not expected_complete:
                saw_partial = True
            assert category["keys_complete"] is expected_complete, (
                f"{domain_entry['domain']}.{category['name']}: "
                f"len(sample)={len(sample)}, count={count}, "
                f"keys_complete={category['keys_complete']}"
            )
    assert saw_partial, "Expected at least one partial category in knowledge_catalog"

    limit_params = _discover_limit_params(spec)
    sample_limit_param = next(
        (name for name in limit_params if "sample" in name or "limit" in name),
        None,
    )
    if sample_limit_param is not None:
        small_res = call_python_run(
            tool_name,
            {sample_limit_param: 3},
            as_of=e2e_as_of,
            include=["*"],
        )
        large_res = call_python_run(
            tool_name,
            {sample_limit_param: 10},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert small_res.ok and large_res.ok
        small_samples: dict[tuple[str, str], int] = {}
        large_samples: dict[tuple[str, str], int] = {}
        for res_obj, sink in (
            (small_res.payload, small_samples),
            (large_res.payload, large_samples),
        ):
            max_allowed = 3 if sink is small_samples else 10
            for domain_entry in res_obj["domains"]:
                for category in domain_entry["categories"]:
                    sample = (
                        category["keys_sample"]
                        if "keys_sample" in category
                        else category["keys"]
                    )
                    assert len(sample) <= max_allowed
                    assert category["keys_complete"] is (
                        len(sample) == category["count"]
                    )
                    if category["count"] >= 10:
                        sink[(domain_entry["domain"], category["name"])] = len(sample)
        assert small_samples and all(
            small_samples[key] < large_samples[key] for key in small_samples
        )


def test_r3_solar_terms_for_year_clean_filtering_without_duplication(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "solar_terms_for_year"
    base_payload = augmented_inputs_for(tool_name, all_tool_specs)
    year = int(base_payload.get("year", 2026))

    unfiltered = call_python_run(
        tool_name, {"year": year, "jieqis": []}, as_of=e2e_as_of, include=["*"]
    )
    filtered = call_python_run(
        tool_name,
        {"year": year, "jieqis": ["立春", "春分"]},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert unfiltered.ok and filtered.ok

    unfiltered_biz = strip_run_metadata(unfiltered.payload)
    unfiltered_term_lists = [
        (k, v)
        for k, v in unfiltered_biz.items()
        if isinstance(v, list) and len(v) == 24
    ]
    assert len(unfiltered_term_lists) == 1, (
        f"Expected single 24-term list when jieqis=[] (no duplicate block), "
        f"found {[k for k, _ in unfiltered_term_lists]}"
    )

    filtered_biz = strip_run_metadata(filtered.payload)
    filtered_term_lists = [
        (k, v)
        for k, v in filtered_biz.items()
        if isinstance(v, list)
        and v
        and isinstance(v[0], dict)
        and ("name" in v[0] or "jieqi" in v[0] or "term" in v[0])
    ]
    assert len(filtered_term_lists) == 1, (
        f"Expected only the filtered solar-term list without redundant full "
        f"24-term block, found {[(k, len(v)) for k, v in filtered_term_lists]}"
    )
    _, selected_items = filtered_term_lists[0]
    assert len(selected_items) == 2
    extracted_names = [
        item.get("name") or item.get("jieqi") or item.get("term")
        for item in selected_items
    ]
    assert extracted_names == ["立春", "春分"]


def test_r4_discovered_call_guidance_matches_live_surfaces(
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    """Opaque-box guard ensuring discovered call_guidance contains no retired R4 paths."""
    import json

    global_forbidden = (
        "stage_variants",
        "natal_ruler_contexts",
        "moon_readings",
        "timezone_basis",
        "configuration_not_supported",
        "yuddha_bala.evidence",
        "upstream_profile",
        "solar_events.enumeration",
        "wealth_components",
        "selected_readings.source_witnesses",
        "research_validation",
        "additional_profile_audits",
        "time_scope_comparison",
        "current_profile_study",
        "reference_baseline_supplement",
        "ziwei_birth.limit_reading",
        "source_comparison.matches_source_record",
        "ephemeris_provenance",
        "ephemeris_model_scope",
        "nonphysical_factor_models",
        "native_execution_context",
        "ephemeris_source_summary",
        "guolao_research_v7",
        "chart_variant=germany",
        "hinoo_source",
        "printed_edition_reference",
        "purple_model_audit",
        "active_primary_evidence",
        "downloaded_primary_edition",
        "cached_primary_excerpt",
        "manuscript_month_header",
        "manuscript_daily_annotations",
        "include_calculation_reading",
        "calculation_reading",
        "gate_activation_context",
        "local_root_family_summary",
        "numerical_precision",
        "natal_palace_ganzhi",
        "natal_star_label",
        "midpoint_analysis.time_sensitivity",
        "liureng.month_general",
        "liureng.branch_relations",
        "scopes.palace_name",
        "palace_map.scope_palace_name",
        "ziwei_horoscope.calendar_basis.time_input",
        "activations[*].ephemeris_model",
        "source_clock",
        "physical_clock_applied",
        "calendar_mapping_complete",
        "hexagram_entry",
        "pure_trigram_rule",
        "source_issues",
        "not_adjudicated",
        "profile.input_clock",
        "hypothetical_element_source",
        "seorbel.txt",
    )
    for tool_name, spec in sorted(all_tool_specs.items()):
        guidance_blob = json.dumps(spec.get("call_guidance") or {}, ensure_ascii=False)
        views_blob = json.dumps(spec.get("evidence_views") or {}, ensure_ascii=False)
        for token in global_forbidden:
            assert (
                token not in guidance_blob
            ), f"{tool_name} call_guidance leaked retired token {token!r}"
            assert (
                token not in views_blob
            ), f"{tool_name} evidence_views leaked retired token {token!r}"

    astro_guidance = json.dumps(
        all_tool_specs["astrology_chart"].get("call_guidance") or {},
        ensure_ascii=False,
    )
    for token in (
        "midpoint_analysis.profile.angle_definition",
        "mixed_pair_geometry",
        "comparative_geometry",
        "daily_meridian",
        "birth_time_sensitivity.status",
    ):
        assert token not in astro_guidance

    for bazi_topic in (
        "bazi_health",
        "bazi_wealth",
        "bazi_marriage",
        "bazi_romance",
        "bazi_education",
        "bazi_personality",
        "bazi_relatives",
        "bazi_children",
    ):
        topic_name = bazi_topic.removeprefix("bazi_")
        blob = json.dumps(
            all_tool_specs[bazi_topic].get("call_guidance") or {}, ensure_ascii=False
        )
        assert f"{topic_name}_analysis.topic_facts" in blob
        assert f"{topic_name}_analysis.timing_context" in blob
        for stale in (
            "evidence_chain",
            "structure_checks",
            "topic.timing",
            "clash_present",
            "classical_context",
        ):
            assert stale not in blob, f"{bazi_topic} call_guidance leaked {stale!r}"

    vedic_guidance = json.dumps(
        all_tool_specs["vedic_chart"].get("call_guidance") or {}, ensure_ascii=False
    )
    assert "2,3,4,7,9,10,12,16,20,24,27,30,40,45,60" in vedic_guidance
    assert "birth_time_uncertainty_minutes" not in vedic_guidance

    dasha_guidance = json.dumps(
        all_tool_specs["vimshottari_dasha"].get("call_guidance") or {},
        ensure_ascii=False,
    )
    assert "birth_time_uncertainty_minutes" not in dasha_guidance

    import re

    thirteen_guidance = json.dumps(
        all_tool_specs["thirteen_sector_chart"].get("call_guidance") or {},
        ensure_ascii=False,
    )
    assert "sector_profile.anchor_longitude" in thirteen_guidance
    assert not re.search(r"(?<![a-z_])profile\.anchor_longitude", thirteen_guidance)

    liuren_schema_blob = json.dumps(
        all_tool_specs["liuren_chart"].get("output_schema") or {},
        ensure_ascii=False,
    )
    assert "liureng.branch_relations" not in liuren_schema_blob

    hd_guidance = json.dumps(
        all_tool_specs["human_design"].get("call_guidance") or {},
        ensure_ascii=False,
    )
    assert "activations.personality[*]" in hd_guidance
    assert "activations.design[*]" in hd_guidance

    ziwei_timing_guidance = json.dumps(
        all_tool_specs["ziwei_timing"].get("call_guidance") or {},
        ensure_ascii=False,
    )
    assert "scopes[*].natal_palace_name" in ziwei_timing_guidance
    assert (
        "ziwei_horoscope.calendar_basis.{birth,target}.time_input"
        in ziwei_timing_guidance
    )

    for meihua_tool in ("meihua_time_cast", "meihua_cast"):
        weather_text = str(
            (all_tool_specs[meihua_tool].get("call_guidance") or {}).get("weather")
            or ""
        )
        assert "interpretation.comprehensive_judgement" in weather_text

    heluo_guidance = json.dumps(
        all_tool_specs["heluo"].get("call_guidance") or {}, ensure_ascii=False
    )
    assert "cycleYear" not in heluo_guidance
    assert "heluo_timing.year_context" in heluo_guidance

    guolao_guidance = json.dumps(
        all_tool_specs["guolao_chart"].get("call_guidance") or {}, ensure_ascii=False
    )
    assert "longitude_speed_native" not in guolao_guidance

    hamburg_spec = all_tool_specs["hamburg_midpoint_chart"]
    hamburg_comp_when = str(
        (hamburg_spec.get("evidence_views") or {})
        .get("comparative_geometry", {})
        .get("when")
        or ""
    )
    assert "birth_time_uncertainty_minutes" in hamburg_comp_when
    hamburg_schema_blob = json.dumps(
        hamburg_spec.get("output_schema") or {}, ensure_ascii=False
    )
    assert "hypothetical_element_source" not in hamburg_schema_blob


def test_r5_hamburg_live_sample_references_use_birth_time_sensitivity(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """Live hamburg_midpoint_chart sample references must cite midpoint_analysis.birth_time_sensitivity.samples."""
    import json

    base = dict(all_tool_specs["hamburg_midpoint_chart"]["example_input"])
    res = call_python_run(
        "hamburg_midpoint_chart",
        {
            **base,
            "birth_time_uncertainty_minutes": 10,
            "analysis_datetime": "2026-06-01T12:00:00+08:00",
        },
        as_of=e2e_as_of,
        include=["*"],
    )
    assert res.ok, res.payload
    blob = json.dumps(res.payload, ensure_ascii=False)
    assert "midpoint_analysis.time_sensitivity.samples" not in blob
    assert "midpoint_analysis.birth_time_sensitivity.samples" in blob


def test_r6_heluo_and_guolao_live_runtime_fields(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """Live heluo timing/najia and guolao_chart profile fields match updated guidance and docs."""
    heluo_base = dict(all_tool_specs["heluo"]["example_input"])
    heluo_res = call_python_run(
        "heluo",
        {**heluo_base, "analysis_year": 1990, "month_index": 1, "day_index": 1},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert heluo_res.ok, heluo_res.payload
    year_context = heluo_res.payload["heluo_timing"]["year_context"]
    assert "cycle_year" in year_context and "cycleYear" not in year_context
    assert "source_clock" not in heluo_res.payload["heluo_timing"]
    najia_entry = heluo_res.payload["judge"]["najia"][0]
    assert "source_issues" not in najia_entry
    assert set(najia_entry["lines"][0]) == {"pos", "trigram", "direct", "borrowed"}

    guolao_base = dict(all_tool_specs["guolao_chart"]["example_input"])
    guolao_res = call_python_run(
        "guolao_chart", guolao_base, as_of=e2e_as_of, include=["*"]
    )
    assert guolao_res.ok, guolao_res.payload
    profile = guolao_res.payload["guolao"]["profile"]
    assert "time_conversion" in profile and "input_clock" not in profile
    assert "clock_basis" in guolao_res.payload["guolao"]["life_palace"]


def test_r7_hamburg_comparative_geometry_and_fictitious_elements(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """hamburg_midpoint_chart comparative_geometry works with birth_time_uncertainty_minutes=10 and emits real hypothetical factor fields."""
    hamburg_spec = all_tool_specs["hamburg_midpoint_chart"]
    base = dict(hamburg_spec["example_input"])
    payload = {**base, "birth_time_uncertainty_minutes": 10}
    comp_fields = list(hamburg_spec["evidence_views"]["comparative_geometry"]["fields"])

    inc_res = call_python_run(
        "hamburg_midpoint_chart",
        payload,
        as_of=e2e_as_of,
        include=["comparative_geometry"],
    )
    fld_res = call_python_run(
        "hamburg_midpoint_chart",
        payload,
        as_of=e2e_as_of,
        fields=comp_fields,
    )
    full_res = call_python_run(
        "hamburg_midpoint_chart",
        payload,
        as_of=e2e_as_of,
        include=["*"],
    )
    assert inc_res.ok, inc_res.payload
    assert fld_res.ok, fld_res.payload
    assert full_res.ok, full_res.payload

    for res in (inc_res, fld_res, full_res):
        comp = res.payload["midpoint_analysis"]["comparative_geometry"]
        assert comp["birth_time_sensitivity"]["status"] == "sampled"

    full_ma = full_res.payload["midpoint_analysis"]
    assert "hypothetical_element_source" not in full_ma["profile"]
    assert "hypothetical_element_source" not in full_ma["birth_time_sensitivity"]
    hypothetical_factors = [
        factor for factor in full_ma["factors"] if factor.get("kind") == "hypothetical"
    ]
    assert len(hypothetical_factors) == 8
    for factor in hypothetical_factors:
        assert factor.get("model") == "swisseph_fictitious_elements"
        assert isinstance(factor.get("element_name"), str) and factor["element_name"]
