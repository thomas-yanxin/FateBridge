"""Tests for M6 Plan A contracts: R2/R3/R4 across western_timing, western_lifespan, and western_event."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import evidence_views, example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.requests.western_timing import (
    WesternPrimaryDirectionsChartRequest,
    WesternPrimaryDirectionsRequest,
)
from fatebridge.services.tool_catalog import CATALOG

M6_FAMILIES = frozenset({"western_timing", "western_lifespan", "western_event"})
M6_SPECS = [spec for spec in CATALOG if spec.family in M6_FAMILIES]
SPECS_BY_NAME = {spec.name: spec for spec in M6_SPECS}
AS_OF = "2026-10-12T12:00:00+08:00"

DEMO_BIRTH: dict[str, Any] = {
    "name": "演示甲",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 116.4074,
    "birth_latitude": 39.9042,
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 14,
    "analysis_hour": 12,
    "analysis_minute": 0,
}


def _assert_isomorphic_subset(subset: object, full: object, *, path: str = "") -> None:
    if isinstance(subset, dict):
        assert isinstance(full, dict), f"Type mismatch at {path}"
        for key, value in subset.items():
            assert key in full, f"Unexpected non-isomorphic key {path}.{key}"
            if path == "" and key == "run_metadata":
                continue
            _assert_isomorphic_subset(
                value, full[key], path=f"{path}.{key}" if path else key
            )
    elif isinstance(subset, list):
        assert isinstance(full, list), f"Type mismatch at {path}"
        assert len(subset) == len(full), f"List length mismatch at {path}"
        for idx, (sub_item, full_item) in enumerate(zip(subset, full)):
            _assert_isomorphic_subset(sub_item, full_item, path=f"{path}[{idx}]")
    else:
        assert subset == full, f"Value mismatch at {path}: {subset!r} != {full!r}"


@pytest.mark.parametrize("spec", M6_SPECS, ids=lambda spec: spec.name)
def test_m6_tools_default_delivery_budget_isomorphism_and_includes(spec) -> None:
    example = example_input(spec)
    assert example is not None
    req = spec.request_model.model_validate(example)
    raw = execute_with_receipt(spec, req, options=ExecutionOptions(as_of=AS_OF))

    default_out = deliver_response(raw, spec=spec)
    full_out = deliver_response(raw, spec=spec, include=["*"])

    default_bytes = len(json.dumps(default_out, ensure_ascii=False).encode("utf-8"))
    assert default_bytes <= 10240, f"{spec.name} default size {default_bytes} > 10240"

    assert "omitted_fields" not in full_out["run_metadata"]
    omitted = default_out["run_metadata"].get("omitted_fields")
    if spec.default_omit:
        assert omitted, f"{spec.name} expected omitted_fields"
    else:
        assert omitted is None

    _assert_isomorphic_subset(default_out, full_out)

    for pattern in spec.default_omit:
        unomitted = deliver_response(raw, spec=spec, include=[pattern])
        remaining = unomitted["run_metadata"].get("omitted_fields") or []
        assert pattern not in remaining

    for view_name in evidence_views(spec) or {}:
        deliver_response(raw, spec=spec, include=[view_name])


def test_horary_and_election_heavy_variants_stay_under_budget() -> None:
    opts = ExecutionOptions(as_of=AS_OF)

    horary_spec = SPECS_BY_NAME["horary_chart"]
    horary_req = horary_spec.request_model.model_validate(
        {**example_input(horary_spec), "category": "marriage", "turned_from_house": 5}
    )
    horary_raw = execute_with_receipt(horary_spec, horary_req, options=opts)
    horary_default = deliver_response(horary_raw, spec=horary_spec)
    horary_full = deliver_response(horary_raw, spec=horary_spec, include=["*"])
    assert len(json.dumps(horary_default, ensure_ascii=False).encode("utf-8")) <= 10240
    _assert_isomorphic_subset(horary_default, horary_full)

    election_spec = SPECS_BY_NAME["evaluate_election_time"]
    election_req = election_spec.request_model.model_validate(
        {
            **example_input(election_spec),
            "topic_id": "marriage",
            "search_window_hours": 48,
        }
    )
    election_raw = execute_with_receipt(election_spec, election_req, options=opts)
    election_default = deliver_response(election_raw, spec=election_spec)
    election_full = deliver_response(election_raw, spec=election_spec, include=["*"])
    assert (
        len(json.dumps(election_default, ensure_ascii=False).encode("utf-8")) <= 10240
    )
    _assert_isomorphic_subset(election_default, election_full)


def test_western_timing_r3_scope_to_input_and_no_parameter_leakage() -> None:
    opts = ExecutionOptions(as_of=AS_OF)

    # 1. No parameter leakage onto unrelated split models.
    for clean_tool in (
        "solar_return",
        "lunar_return",
        "profection",
        "firdaria",
        "decennials",
        "zodiacal_releasing",
    ):
        fields = set(SPECS_BY_NAME[clean_tool].request_model.model_fields)
        assert "orb_limit" not in fields
        assert "max_hits" not in fields
        assert not any(name.startswith("pd_") for name in fields)

    # 2. transit_chart respects orb_limit, max_hits, and emits *_total_count.
    transit_spec = SPECS_BY_NAME["transit_chart"]
    full_tc = execute_with_receipt(
        transit_spec,
        transit_spec.request_model.model_validate(
            {**DEMO_BIRTH, "orb_limit": 3.0, "scan_days": 3}
        ),
        options=opts,
    )["transit_chart"]
    capped_tc = execute_with_receipt(
        transit_spec,
        transit_spec.request_model.model_validate(
            {**DEMO_BIRTH, "orb_limit": 3.0, "max_hits": 2, "scan_days": 3}
        ),
        options=opts,
    )["transit_chart"]
    assert full_tc["hits_total_count"] == len(full_tc["hits"])
    assert full_tc["exact_hits_total_count"] == len(full_tc["exact_hits"])
    assert capped_tc["hits_total_count"] == full_tc["hits_total_count"]
    assert len(capped_tc["hits"]) <= 2
    assert len(capped_tc["exact_hits"]) <= 2
    for full_step, capped_step in zip(
        full_tc["transit_timeline"], capped_tc["transit_timeline"]
    ):
        assert full_step["exact_hits_total_count"] == len(full_step["exact_hits"])
        assert full_step["tight_hits_total_count"] == len(full_step["tight_hits"])
        assert (
            capped_step["tight_hits_total_count"] == full_step["tight_hits_total_count"]
        )
        assert len(capped_step["tight_hits"]) <= 2

    # 3. solar_arc & chart_for_year respect orb_limit and max_hits.
    for tool_name in ("solar_arc", "chart_for_year"):
        spec = SPECS_BY_NAME[tool_name]
        full_payload = execute_with_receipt(
            spec,
            spec.request_model.model_validate({**DEMO_BIRTH, "orb_limit": 3.0}),
            options=opts,
        )[tool_name]
        capped_payload = execute_with_receipt(
            spec,
            spec.request_model.model_validate(
                {**DEMO_BIRTH, "orb_limit": 3.0, "max_hits": 2}
            ),
            options=opts,
        )[tool_name]
        assert full_payload["hits_total_count"] == len(full_payload["hits"])
        assert capped_payload["hits_total_count"] == full_payload["hits_total_count"]
        assert len(capped_payload["hits"]) <= 2

    # 4. primary_directions & primary_directions_chart respect pd_* params & counts.
    pd_spec = SPECS_BY_NAME["primary_directions"]
    pd_payload = execute_with_receipt(
        pd_spec,
        pd_spec.request_model.model_validate(
            {**DEMO_BIRTH, "pd_window_size": 4, "pd_max_age_years": 60.0}
        ),
        options=opts,
    )["primary_directions"]
    assert len(pd_payload["current_window"]) == 4
    assert (
        pd_payload["current_window_total_count"] == pd_payload["total_timeline_count"]
    )
    assert pd_payload["past_window_total_count"] >= len(pd_payload["past_window"])
    assert pd_payload["future_window_total_count"] >= len(pd_payload["future_window"])
    assert pd_payload["exact_window_total_count"] >= len(pd_payload["exact_window"])

    pdc_spec = SPECS_BY_NAME["primary_directions_chart"]
    pdc_payload = execute_with_receipt(
        pdc_spec,
        pdc_spec.request_model.model_validate({**DEMO_BIRTH, "pd_window_size": 4}),
        options=opts,
    )["primary_directions_chart"]
    assert len(pdc_payload["hits"]) == 4
    assert len(pdc_payload["coordinate_hits"]) == 4
    assert pdc_payload["hits_total_count"] >= 4
    assert pdc_payload["exact_hits_total_count"] >= len(pdc_payload["exact_hits"])

    # 5. western_timing respects pd_timeline_limit and pd_nearby_years.
    wt_spec = SPECS_BY_NAME["western_timing"]
    wt_pd = execute_with_receipt(
        wt_spec,
        wt_spec.request_model.model_validate(
            {
                **DEMO_BIRTH,
                "techniques": ["primary_directions"],
                "pd_nearby_years": 20.0,
                "pd_timeline_limit": 5,
            }
        ),
        options=opts,
    )["directions"]["primary_directions"]
    assert len(wt_pd["timeline"]) == 5
    assert wt_pd["timeline_truncated"] is True

    # 6. primary_directions_chart omits timeline-only scope fields; standalone
    # primary_directions honors pd_timeline_limit, pd_nearby_years, and include_full_timelines.
    for forbidden_field in (
        "pd_nearby_years",
        "pd_timeline_limit",
        "include_full_timelines",
    ):
        assert forbidden_field not in WesternPrimaryDirectionsChartRequest.model_fields
        with pytest.raises(ValidationError):
            WesternPrimaryDirectionsChartRequest.model_validate(
                {
                    **DEMO_BIRTH,
                    forbidden_field: (
                        5 if forbidden_field != "include_full_timelines" else True
                    ),
                }
            )
    assert "pd_nearby_years" in WesternPrimaryDirectionsRequest.model_fields
    assert "pd_timeline_limit" in WesternPrimaryDirectionsRequest.model_fields
    assert "include_full_timelines" in WesternPrimaryDirectionsRequest.model_fields

    pd_narrow_raw = execute_with_receipt(
        pd_spec,
        pd_spec.request_model.model_validate(
            {**DEMO_BIRTH, "pd_timeline_limit": 5, "pd_nearby_years": 2.0}
        ),
        options=opts,
    )
    pd_narrow = deliver_response(
        pd_narrow_raw, spec=pd_spec, include=["primary_directions.timeline"]
    )["primary_directions"]
    assert len(pd_narrow["timeline"]) == 5
    assert pd_narrow["timeline_truncated"] is True
    assert pd_narrow["total_timeline_count"] > 50

    pd_wide_raw = execute_with_receipt(
        pd_spec,
        pd_spec.request_model.model_validate(
            {**DEMO_BIRTH, "pd_timeline_limit": 50, "pd_nearby_years": 20.0}
        ),
        options=opts,
    )
    pd_wide = deliver_response(
        pd_wide_raw, spec=pd_spec, include=["primary_directions.timeline"]
    )["primary_directions"]
    assert len(pd_wide["timeline"]) == 50
    assert pd_wide["timeline_truncated"] is True
    assert pd_wide["total_timeline_count"] == pd_narrow["total_timeline_count"]

    pd_full_raw = execute_with_receipt(
        pd_spec,
        pd_spec.request_model.model_validate(
            {**DEMO_BIRTH, "include_full_timelines": True}
        ),
        options=opts,
    )
    pd_full = deliver_response(
        pd_full_raw, spec=pd_spec, include=["primary_directions.timeline"]
    )["primary_directions"]
    assert len(pd_full["timeline"]) == pd_full["total_timeline_count"]
    assert pd_full["total_timeline_count"] == pd_narrow["total_timeline_count"]
    assert "timeline_truncated" not in pd_full

    # 7. transit_chart summary uses pre-cap exact_hits_total_count when scan_days + max_hits combine.
    tc_scan_capped = execute_with_receipt(
        transit_spec,
        transit_spec.request_model.model_validate(
            {**DEMO_BIRTH, "scan_days": 14, "max_hits": 1}
        ),
        options=opts,
    )
    tc_timeline = tc_scan_capped["transit_chart"]["transit_timeline"]
    expected_exact_total = sum(step["exact_hits_total_count"] for step in tc_timeline)
    returned_exact_total = sum(len(step["exact_hits"]) for step in tc_timeline)
    assert expected_exact_total > returned_exact_total
    assert (
        f"扫描 14 天共 {expected_exact_total} 次精确命中" in tc_scan_capped["summary"]
    )


def test_western_lifespan_and_events_r3_scope_to_input_and_counts() -> None:
    opts = ExecutionOptions(as_of=AS_OF)
    lifespan_date_birth = {
        k: v
        for k, v in DEMO_BIRTH.items()
        if k not in {"analysis_hour", "analysis_minute"}
    }

    # 1. planetary_arc_directions: max_hits & hits_total_count
    pa_spec = SPECS_BY_NAME["planetary_arc_directions"]
    pa_full = execute_with_receipt(
        pa_spec,
        pa_spec.request_model.model_validate({**lifespan_date_birth, "orb": 5.0}),
        options=opts,
    )["planetary_arc"]
    pa_cap = execute_with_receipt(
        pa_spec,
        pa_spec.request_model.model_validate(
            {**lifespan_date_birth, "orb": 5.0, "max_hits": 2}
        ),
        options=opts,
    )["planetary_arc"]
    assert pa_full["hits_total_count"] == len(pa_full["hits"]) > 2
    assert pa_cap["hits_total_count"] == pa_full["hits_total_count"]
    assert len(pa_cap["hits"]) == 2

    # 2. sidereal_progressions: max_hits & hits_total_count
    sp_spec = SPECS_BY_NAME["sidereal_progressions"]
    sp_full = execute_with_receipt(
        sp_spec,
        sp_spec.request_model.model_validate({**lifespan_date_birth, "orb": 5.0}),
        options=opts,
    )["sidereal_progressions"]
    sp_cap = execute_with_receipt(
        sp_spec,
        sp_spec.request_model.model_validate(
            {**lifespan_date_birth, "orb": 5.0, "max_hits": 2}
        ),
        options=opts,
    )["sidereal_progressions"]
    assert sp_full["hits_total_count"] == len(sp_full["hits"]) > 2
    assert sp_cap["hits_total_count"] == sp_full["hits_total_count"]
    assert len(sp_cap["hits"]) == 2

    # 3. persian_directions: limit (default 120, None for all) & hits_total_count
    persian_spec = SPECS_BY_NAME["persian_directions"]
    persian_base = {
        k: v for k, v in DEMO_BIRTH.items() if not k.startswith("analysis_")
    }
    persian_default = execute_with_receipt(
        persian_spec,
        persian_spec.request_model.model_validate(persian_base),
        options=opts,
    )["persian_directions"]
    persian_all = execute_with_receipt(
        persian_spec,
        persian_spec.request_model.model_validate({**persian_base, "limit": None}),
        options=opts,
    )["persian_directions"]
    assert persian_default["hit_count"] == 120
    assert persian_default["hits_total_count"] > 120
    assert persian_all["hit_count"] == persian_all["hits_total_count"]
    assert len(persian_all["hits"]) == persian_all["hits_total_count"]

    # 4. Omitted-by-default list counts on lifespan tools
    lp_spec = SPECS_BY_NAME["lunar_phase_progressions"]
    lp_payload = execute_with_receipt(
        lp_spec,
        lp_spec.request_model.model_validate(example_input(lp_spec)),
        options=opts,
    )["lunar_phase_progressions"]
    assert lp_payload["phase_ingress_count"] == len(lp_payload["phase_ingresses"])

    kp_spec = SPECS_BY_NAME["numeric_aspect_periods"]
    kp_payload = execute_with_receipt(
        kp_spec,
        kp_spec.request_model.model_validate(example_input(kp_spec)),
        options=opts,
    )["numeric_aspect_periods"]
    assert kp_payload["activation_count"] == len(kp_payload["activations"])

    ap_spec = SPECS_BY_NAME["age_point"]
    ap_payload = execute_with_receipt(
        ap_spec,
        ap_spec.request_model.model_validate(example_input(ap_spec)),
        options=opts,
    )["age_point"]
    assert ap_payload["point_count"] == len(ap_payload["points"])

    # 5. evaluate_election_time: max_candidate_windows & candidate_windows_total_count
    el_spec = SPECS_BY_NAME["evaluate_election_time"]
    el_ex = example_input(el_spec)
    el_default = execute_with_receipt(
        el_spec,
        el_spec.request_model.model_validate({**el_ex, "search_window_hours": 10}),
        options=opts,
    )["election"]
    el_all = execute_with_receipt(
        el_spec,
        el_spec.request_model.model_validate(
            {**el_ex, "search_window_hours": 10, "max_candidate_windows": None}
        ),
        options=opts,
    )["election"]
    assert el_default["candidate_windows_total_count"] == 11
    assert len(el_default["candidate_windows"]) == 5
    assert el_all["candidate_windows_total_count"] == 11
    assert len(el_all["candidate_windows"]) == 11
