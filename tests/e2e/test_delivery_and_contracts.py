"""Opaque-box E2E tests for M2 (91-tool delivery, isomorphism, <=10 KiB budget & R3 scope)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e.conftest import (
    AUGMENTED_TOOL_INPUTS,
    EXTRA_DOMAIN_INPUTS,
    assert_dotted_path_restored,
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest,
    find_bloat_keys,
    get_all_full_specs,
    has_dotted_path,
    rest_path_for,
    strip_run_metadata,
)

DEFAULT_PAYLOAD_BUDGET_BYTES = 10_240
ALL_TOOL_NAMES: tuple[str, ...] = tuple(sorted(get_all_full_specs()))

SUPPLEMENTAL_MODES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("ipip_big_five_score", "ipip_big_five", AUGMENTED_TOOL_INPUTS["ipip_big_five"]),
    ("ipip_big_five_list", "ipip_big_five", EXTRA_DOMAIN_INPUTS["ipip_big_five_list"]),
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
    (
        "fengshui_monthly_stars_instant",
        "fengshui_monthly_stars",
        EXTRA_DOMAIN_INPUTS["fengshui_monthly_stars_instant"],
    ),
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


def _assert_default_vs_full_invariants(
    label: str,
    default_payload: dict[str, Any],
    full_payload: dict[str, Any],
) -> None:
    assert find_bloat_keys(default_payload) == [], f"{label} default leaked bloat keys"
    assert find_bloat_keys(full_payload) == [], f"{label} full leaked bloat keys"

    default_bytes = len(json.dumps(default_payload, ensure_ascii=False).encode("utf-8"))
    assert (
        default_bytes <= DEFAULT_PAYLOAD_BUDGET_BYTES
    ), f"{label} default payload size {default_bytes}B exceeds {DEFAULT_PAYLOAD_BUDGET_BYTES}B"

    default_biz = strip_run_metadata(default_payload)
    full_biz = strip_run_metadata(full_payload)
    assert_isomorphic_subset(default_biz, full_biz)

    assert not full_payload.get("run_metadata", {}).get(
        "omitted_fields"
    ), f"{label} include=['*'] must not report omitted_fields"

    default_omitted = default_payload.get("run_metadata", {}).get("omitted_fields")
    if default_biz != full_biz:
        assert (
            isinstance(default_omitted, list) and len(default_omitted) > 0
        ), f"{label}: default differs from include=['*'] without omitted_fields"
    if default_omitted is not None:
        assert isinstance(default_omitted, list)
        for omitted_path in default_omitted:
            assert isinstance(omitted_path, str) and omitted_path
            assert not has_dotted_path(
                default_biz, omitted_path
            ), f"{label}: {omitted_path!r} still in default"
            assert has_dotted_path(
                full_biz, omitted_path
            ), f"{label}: {omitted_path!r} missing in include=['*']"


# ---------------------------------------------------------------------------
# M2: 91-Tool & 6-Mode Isomorphism, `omitted_fields`, Hygiene & <=10 KiB Budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", ALL_TOOL_NAMES)
def test_all_91_tools_default_vs_full_budget_and_hygiene(
    tool_name: str,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    example = all_tool_specs[tool_name].get("example_input")
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
def test_supplemental_modes_default_vs_full_budget_and_hygiene(
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


# ---------------------------------------------------------------------------
# M2: Evidence Views & Wildcard `default_omit` Restoration
# ---------------------------------------------------------------------------


def test_all_tools_evidence_views_and_wildcard_default_omit(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name, spec in sorted(all_tool_specs.items()):
        views = spec.get("evidence_views") or {}
        if not views:
            continue
        example_payload = dict(spec.get("example_input") or {})
        full_out = call_python_run(
            tool_name, example_payload, as_of=e2e_as_of, include=["*"]
        )
        assert full_out.ok, f"{tool_name} include=['*'] failed: {full_out.payload}"

        for view_name, view_card in sorted(views.items()):
            fields_list = list(view_card.get("fields") or [])
            assert fields_list, f"{tool_name}.{view_name} empty fields"
            if "when" in view_card:
                continue
            inc_out = call_python_run(
                tool_name, example_payload, as_of=e2e_as_of, include=[view_name]
            )
            fld_out = call_python_run(
                tool_name, example_payload, as_of=e2e_as_of, fields=fields_list
            )
            assert inc_out.ok, f"{tool_name} include=[{view_name!r}] failed"
            assert fld_out.ok, f"{tool_name} fields={fields_list!r} failed"
            assert_isomorphic_subset(inc_out.payload, full_out.payload)
            assert_isomorphic_subset(fld_out.payload, full_out.payload)
            inc_omitted = (
                inc_out.payload.get("run_metadata", {}).get("omitted_fields") or []
            )
            for fp in fields_list:
                if has_dotted_path(full_out.payload, fp):
                    assert has_dotted_path(
                        inc_out.payload, fp
                    ), f"{tool_name} include=[{view_name!r}] missing {fp!r}"
                    assert has_dotted_path(
                        fld_out.payload, fp
                    ), f"{tool_name} fields={fields_list!r} missing {fp!r}"
                    assert (
                        fp not in inc_omitted
                    ), f"{tool_name} include=[{view_name!r}] left {fp!r} in omitted_fields"

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
            "interpretation": {"current_period_number": 9}
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
        assert "when" in view_card
        fields_list = list(view_card.get("fields") or [])
        assert fields_list, f"{tool_name}.{view_name} empty fields"
        call_payload = {**augmented_inputs_for(tool_name, all_tool_specs), **override}
        full_out = call_python_run(
            tool_name, call_payload, as_of=e2e_as_of, include=["*"]
        )
        inc_out = call_python_run(
            tool_name, call_payload, as_of=e2e_as_of, include=[view_name]
        )
        fld_out = call_python_run(
            tool_name, call_payload, as_of=e2e_as_of, fields=fields_list
        )
        assert full_out.ok and inc_out.ok and fld_out.ok
        assert_isomorphic_subset(inc_out.payload, full_out.payload)
        assert_isomorphic_subset(fld_out.payload, full_out.payload)
        inc_omitted = (
            inc_out.payload.get("run_metadata", {}).get("omitted_fields") or []
        )
        for fp in fields_list:
            if has_dotted_path(full_out.payload, fp):
                assert has_dotted_path(
                    inc_out.payload, fp
                ), f"{tool_name} include=[{view_name!r}] missing {fp!r}"
                assert has_dotted_path(
                    fld_out.payload, fp
                ), f"{tool_name} fields={fields_list!r} missing {fp!r}"
                assert (
                    fp not in inc_omitted
                ), f"{tool_name} include=[{view_name!r}] left {fp!r} in omitted_fields"

    for tool_name in ("ziwei_timing", "hamburg_midpoint_chart"):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
        full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
        assert default_out.ok and full_out.ok
        omitted = default_out.payload["run_metadata"].get("omitted_fields") or []
        wildcard_path = next((p for p in omitted if "*" in p), omitted[0])
        restored = call_python_run(
            tool_name, payload, as_of=e2e_as_of, include=[wildcard_path]
        )
        assert restored.ok
        assert_dotted_path_restored(
            strip_run_metadata(default_out.payload),
            strip_run_metadata(restored.payload),
            strip_run_metadata(full_out.payload),
            wildcard_path,
        )
        assert wildcard_path not in (
            restored.payload["run_metadata"].get("omitted_fields") or []
        )


# ---------------------------------------------------------------------------
# M2: 5-Surface Delivery Parity (default / view / dotted / * / fields)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_five_surface_delivery_parity_across_modes(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    view_name = "calendar_basis"
    view_fields = list(all_tool_specs[tool_name]["evidence_views"][view_name]["fields"])
    proj_fields = ["bazi_birth.four_pillars", "bazi_birth.day_master"]

    py_default = call_python_run(tool_name, payload, as_of=e2e_as_of)
    py_full = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert py_default.ok and py_full.ok
    omitted_list = py_default.payload["run_metadata"].get("omitted_fields") or []
    assert omitted_list
    dotted_path = omitted_list[0]

    modes: list[tuple[str, dict[str, Any], list[tuple[str, str]], dict[str, Any]]] = [
        ("default", {}, [("as_of", e2e_as_of)], {}),
        (
            "view",
            {"include": [view_name]},
            [("as_of", e2e_as_of), ("include", view_name)],
            {"include": [view_name]},
        ),
        (
            "dotted",
            {"include": [dotted_path]},
            [("as_of", e2e_as_of), ("include", dotted_path)],
            {"include": [dotted_path]},
        ),
        (
            "star",
            {"include": ["*"]},
            [("as_of", e2e_as_of), ("include", "*")],
            {"include": ["*"]},
        ),
        (
            "fields",
            {"fields": proj_fields},
            [("as_of", e2e_as_of)] + [("fields", f) for f in proj_fields],
            {"fields": proj_fields},
        ),
    ]

    for mode_name, py_kw, rest_params, mcp_ctrl in modes:
        py_out = call_python_run(tool_name, payload, as_of=e2e_as_of, **py_kw)
        mcp_out = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": payload, "as_of": e2e_as_of, **mcp_ctrl},
        )
        rest_out = call_rest(
            rest_client, "POST", rest_path, json_body=payload, params=rest_params
        )
        cli_out = call_cli_tool(tool_name, payload, as_of=e2e_as_of, **py_kw)
        batch_out = await call_mcp_tool(
            mcp_client,
            "run_batch",
            {
                "calls": [
                    {"id": "c1", "tool": tool_name, "arguments": payload, **mcp_ctrl}
                ],
                "as_of": e2e_as_of,
            },
        )

        for out in (py_out, mcp_out, rest_out, cli_out, batch_out):
            assert out.ok, f"{mode_name} failed: {out.payload}"

        batch_result = batch_out.payload["results"][0]["result"]
        expected_biz = strip_run_metadata(py_out.payload)
        for surface_payload in (
            py_out.payload,
            mcp_out.payload,
            rest_out.payload,
            cli_out.payload,
            batch_result,
        ):
            assert strip_run_metadata(surface_payload) == expected_biz
            assert_isomorphic_subset(surface_payload, py_full.payload)
            meta = surface_payload["run_metadata"]
            assert meta["replay"]["as_of"] == e2e_as_of
            assert isinstance(meta["duration_ms"], (int, float))
            if mode_name in {"star", "fields"}:
                assert not meta.get("omitted_fields")
            if mode_name == "view":
                for fp in view_fields:
                    assert has_dotted_path(surface_payload, fp)
                    assert fp not in (meta.get("omitted_fields") or [])
            if mode_name == "dotted":
                assert has_dotted_path(surface_payload, dotted_path)
                assert dotted_path not in (meta.get("omitted_fields") or [])
            if mode_name == "fields":
                assert set(strip_run_metadata(surface_payload)) == {"bazi_birth"}
                assert set(surface_payload["bazi_birth"]) == {
                    "four_pillars",
                    "day_master",
                }


# ---------------------------------------------------------------------------
# M2 / R3: Scope Parameters & Explicit `*_total_count` Bounds
# ---------------------------------------------------------------------------


def _iter_dict_nodes_with_ancestors(
    obj: Any,
    prefix: str = "",
    ancestors: tuple[tuple[str, dict[str, Any]], ...] = (),
) -> Iterator[tuple[str, dict[str, Any], tuple[tuple[str, dict[str, Any]], ...]]]:
    if isinstance(obj, dict):
        yield prefix, obj, ancestors
        next_ancestors = ((prefix, obj), *ancestors)
        for key, value in obj.items():
            yield from _iter_dict_nodes_with_ancestors(
                value, f"{prefix}.{key}" if prefix else str(key), next_ancestors
            )
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _iter_dict_nodes_with_ancestors(
                item, f"{prefix}[{index}]", ancestors
            )


def _assert_total_count_invariants(
    tool_name: str, payload: dict[str, Any], *, expect_equal_when_no_limit: bool
) -> None:
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
            assert isinstance(value, int) and value >= 0
            candidates = (
                stem,
                f"{stem}_contacts",
                f"{stem}_hits",
                f"{stem}_intervals",
                f"{stem}_windows",
                f"{stem}_aspects",
                f"{stem}_activations",
            )
            matched = [node[c] for c in candidates if isinstance(node.get(c), list)]
            if not matched:
                for _, anc_node in ancestors:
                    anc_matched = [
                        anc_node[c]
                        for c in candidates
                        if isinstance(anc_node.get(c), list)
                    ]
                    if anc_matched:
                        matched = anc_matched
                        break
            assert matched, f"{tool_name} {path}.{key}={value} missing list"
            for items in matched:
                assert len(items) <= value
                if expect_equal_when_no_limit:
                    assert len(items) == value


def test_r3_astro_and_western_scope_limits_and_total_counts(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    # 1. astrology_chart max_aspects
    astro_base = augmented_inputs_for("astrology_chart", all_tool_specs)
    astro_full = call_python_run(
        "astrology_chart", astro_base, as_of=e2e_as_of, include=["*"]
    )
    astro_cap = call_python_run(
        "astrology_chart", {**astro_base, "max_aspects": 5}, as_of=e2e_as_of
    )
    assert astro_full.ok and astro_cap.ok
    _assert_total_count_invariants(
        "astrology_chart", astro_full.payload, expect_equal_when_no_limit=True
    )
    _assert_total_count_invariants(
        "astrology_chart", astro_cap.payload, expect_equal_when_no_limit=False
    )
    assert len(astro_cap.payload["aspects"]) == 5
    assert astro_cap.payload["chart_profile"]["aspects_total_count"] == len(
        astro_full.payload["aspects"]
    )

    # 2. transit_chart scan_days (1 vs 90 valid, 0/91 -> 422) & max_hits (2 vs all, 0/201 -> 422)
    tr_base = augmented_inputs_for("transit_chart", all_tool_specs)
    tr_1 = call_python_run(
        "transit_chart", {**tr_base, "scan_days": 1}, as_of=e2e_as_of, include=["*"]
    )
    tr_90 = call_python_run(
        "transit_chart", {**tr_base, "scan_days": 90}, as_of=e2e_as_of, include=["*"]
    )
    tr_full = call_python_run("transit_chart", tr_base, as_of=e2e_as_of, include=["*"])
    tr_cap = call_python_run(
        "transit_chart", {**tr_base, "max_hits": 2}, as_of=e2e_as_of, include=["*"]
    )
    assert tr_1.ok and tr_90.ok and tr_full.ok and tr_cap.ok
    assert len(tr_1.payload["transit_chart"]["transit_timeline"]) == 1
    assert len(tr_90.payload["transit_chart"]["transit_timeline"]) == 90
    _assert_total_count_invariants(
        "transit_chart", tr_full.payload, expect_equal_when_no_limit=True
    )
    _assert_total_count_invariants(
        "transit_chart", tr_cap.payload, expect_equal_when_no_limit=False
    )
    assert len(tr_cap.payload["transit_chart"]["hits"]) == 2
    assert tr_cap.payload["transit_chart"]["hits_total_count"] == len(
        tr_full.payload["transit_chart"]["hits"]
    )
    for invalid in (0, 91):
        err = call_python_run(
            "transit_chart", {**tr_base, "scan_days": invalid}, as_of=e2e_as_of
        )
        assert not err.ok and err.status_code == 422
    for invalid_hits in (0, 201):
        err = call_python_run(
            "transit_chart", {**tr_base, "max_hits": invalid_hits}, as_of=e2e_as_of
        )
        assert not err.ok and err.status_code == 422

    # 3. evaluate_election_time search_window_hours (0 vs 24 valid, -1/169 -> 422)
    el_base = augmented_inputs_for("evaluate_election_time", all_tool_specs)
    el_0 = call_python_run(
        "evaluate_election_time",
        {**el_base, "search_window_hours": 0},
        as_of=e2e_as_of,
        include=["*"],
    )
    el_24 = call_python_run(
        "evaluate_election_time",
        {**el_base, "search_window_hours": 24},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert el_0.ok and el_24.ok
    assert not el_0.payload["election"].get("candidate_windows")
    assert el_24.payload["election"]["candidate_windows_total_count"] >= len(
        el_24.payload["election"]["candidate_windows"]
    )
    for invalid in (-1, 169):
        err = call_python_run(
            "evaluate_election_time",
            {**el_base, "search_window_hours": invalid},
            as_of=e2e_as_of,
        )
        assert not err.ok and err.status_code == 422

    # 4. orb & max_age_years monotonic scope & boundaries
    for tool_name, key_field in (
        ("planetary_arc_directions", "planetary_arc"),
        ("sidereal_progressions", "sidereal_progressions"),
    ):
        base = augmented_inputs_for(tool_name, all_tool_specs)
        c0 = len(
            call_python_run(
                tool_name, {**base, "orb": 0.0}, as_of=e2e_as_of, include=["*"]
            ).payload[key_field]["hits"]
        )
        c15 = len(
            call_python_run(
                tool_name, {**base, "orb": 15.0}, as_of=e2e_as_of, include=["*"]
            ).payload[key_field]["hits"]
        )
        assert c0 < c15
        for bad_orb in (-0.1, 15.1):
            err = call_python_run(tool_name, {**base, "orb": bad_orb}, as_of=e2e_as_of)
            assert not err.ok and err.status_code == 422

    persian_base = augmented_inputs_for("persian_directions", all_tool_specs)
    assert "max_age_years" not in {
        k
        for k in all_tool_specs["persian_directions"]["input_schema"]["properties"]
        if k not in HORIZON_AND_ORB_PARAMS and k.startswith("max_")
    }
    p10 = call_python_run(
        "persian_directions",
        {**persian_base, "max_age_years": 10.0},
        as_of=e2e_as_of,
        include=["*"],
    )
    p200 = call_python_run(
        "persian_directions",
        {**persian_base, "max_age_years": 200.0},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert p10.ok and p200.ok
    assert len(p10.payload["persian_directions"]["hits"]) < len(
        p200.payload["persian_directions"]["hits"]
    )
    for bad_age in (0.0, 200.1):
        err = call_python_run(
            "persian_directions",
            {**persian_base, "max_age_years": bad_age},
            as_of=e2e_as_of,
        )
        assert not err.ok and err.status_code == 422


def test_r3_bazi_knowledge_and_solar_terms_scope_boundaries(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    # bazi_yearly_timing end_year span (<= 20 years)
    yt_base = augmented_inputs_for("bazi_yearly_timing", all_tool_specs)
    y0 = int(yt_base["analysis_year"])
    assert call_python_run(
        "bazi_yearly_timing", {**yt_base, "end_year": y0 + 19}, as_of=e2e_as_of
    ).ok
    yt_err = call_python_run(
        "bazi_yearly_timing", {**yt_base, "end_year": y0 + 20}, as_of=e2e_as_of
    )
    assert not yt_err.ok and yt_err.status_code == 422

    # bazi_monthly_timing scan_months (1..24)
    mt_base = augmented_inputs_for("bazi_monthly_timing", all_tool_specs)
    assert (
        len(
            call_python_run(
                "bazi_monthly_timing", {**mt_base, "scan_months": 1}, as_of=e2e_as_of
            ).payload["monthly_timeline"]
        )
        == 1
    )
    assert (
        len(
            call_python_run(
                "bazi_monthly_timing", {**mt_base, "scan_months": 24}, as_of=e2e_as_of
            ).payload["monthly_timeline"]
        )
        == 24
    )
    for bad_m in (0, 25):
        err = call_python_run(
            "bazi_monthly_timing", {**mt_base, "scan_months": bad_m}, as_of=e2e_as_of
        )
        assert not err.ok and err.status_code == 422

    # bazi_daily_timing scan_days (1..31)
    dt_base = augmented_inputs_for("bazi_daily_timing", all_tool_specs)
    assert (
        len(
            call_python_run(
                "bazi_daily_timing", {**dt_base, "scan_days": 1}, as_of=e2e_as_of
            ).payload["daily_timeline"]
        )
        == 1
    )
    assert (
        len(
            call_python_run(
                "bazi_daily_timing", {**dt_base, "scan_days": 31}, as_of=e2e_as_of
            ).payload["daily_timeline"]
        )
        == 31
    )
    for bad_d in (0, 32):
        err = call_python_run(
            "bazi_daily_timing", {**dt_base, "scan_days": bad_d}, as_of=e2e_as_of
        )
        assert not err.ok and err.status_code == 422

    # knowledge_catalog keys_complete invariant
    kc = call_python_run("knowledge_catalog", {}, as_of=e2e_as_of, include=["*"])
    assert kc.ok
    for dom in kc.payload["domains"]:
        for cat in dom["categories"]:
            sample = cat.get("keys_sample", cat.get("keys"))
            assert cat["keys_complete"] is (len(sample) == cat["count"])

    # solar_terms_for_year jieqis filter
    st = call_python_run(
        "solar_terms_for_year",
        {"year": 2026, "jieqis": ["立春", "春分"]},
        as_of=e2e_as_of,
        include=["*"],
    )
    assert st.ok
    term_lists = [
        v
        for v in strip_run_metadata(st.payload).values()
        if isinstance(v, list) and v and isinstance(v[0], dict)
    ]
    assert len(term_lists) == 1 and len(term_lists[0]) == 2
