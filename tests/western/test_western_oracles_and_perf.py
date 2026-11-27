"""Expert astronomical oracles, contract invariants, and warm latency checks."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import pytest

from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
    calculate_relative_chart_analysis,
)
from fatebridge.services.western_election import calculate_election
from fatebridge.services.western_events import calculate_extrareturns
from fatebridge.services.western_horary import calculate_horary
from fatebridge.services.western_lifespan import calculate_lunation_phase
from fatebridge.services.western_timing_tools import calculate_timing_tool

NATAL_1990 = dict(
    name="Oracle",
    birth_year=1990,
    birth_month=5,
    birth_day=17,
    birth_hour=7,
    birth_minute=30,
    birth_timezone="UTC",
    birth_longitude=-0.1276,
    birth_latitude=51.5072,
)

PROSE_KEYS = frozenset(
    {
        "reading_zh",
        "practical_prompt_zh",
        "conditional_reading_zh",
        "reading_guide",
        "limitations",
    }
)


def _walk_keys(obj: object) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k))
            found |= _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            found |= _walk_keys(item)
    return found


def test_natal_chart_equal_e_poles_motion_oob_nodes_and_profile_size() -> None:
    eq = calculate_core_chart_analysis(
        **NATAL_1990,
        chart_variant="chart",
        house_system="E",
        node_mode="true",
        include_minor_aspects=True,
        extra_bodies=["Chiron", "Ceres", "Lilith", "Pallas"],
    )
    assert "error" not in eq
    assert eq["chart_profile"]["house_system"] == "equal"
    assert eq["chart_profile"]["node_mode"] == "true"
    profile_bytes = len(json.dumps(eq["chart_profile"], ensure_ascii=False).encode())
    assert profile_bytes < 1536, f"chart_profile too large: {profile_bytes} B"

    sun = next(p for p in eq["planets"] if p["id"] == "Sun")
    for field in (
        "longitude_speed",
        "retrograde",
        "stationary",
        "declination",
        "out_of_bounds",
    ):
        assert field in sun
    planet_ids = {p["id"] for p in eq["planets"]}
    assert "Lilith" in planet_ids

    # Check raw pyswisseph True Node parity
    jd_tt = eq["chart_profile"]["julian_day_tt"]
    raw_tn, _ = swe.calc(jd_tt, swe.TRUE_NODE, swe.FLG_SWIEPH | swe.FLG_SPEED)
    node = next(p for p in eq["planets"] if p["id"] == "North Node")
    assert node["longitude"] == pytest.approx(raw_tn[0] % 360.0, abs=1e-6)

    # Geographic pole: Ascendant undefined (None), MC still defined
    pole = calculate_core_chart_analysis(
        **{**NATAL_1990, "birth_latitude": 90.0},
        chart_variant="chart",
        house_system="W",
    )
    assert pole["angles"]["ascendant"]["longitude"] is None
    assert pole["angles"]["midheaven"]["longitude"] is not None
    assert pole["houses"] == []

    # High-latitude quadrant fallback
    arctic = calculate_core_chart_analysis(
        **{**NATAL_1990, "birth_latitude": 70.0},
        chart_variant="chart",
        house_system="P",
        high_latitude_fallback="porphyry",
    )
    assert "error" not in arctic
    assert len(arctic["houses"]) == 12


def test_primary_directions_all_authentic_methods_direct_converse_and_circumpolar() -> (
    None
):
    for method in ("placidus", "regiomontanus", "campanus", "alcabitius", "equatorial"):
        direct_res = calculate_timing_tool(
            tool_name="primary_directions",
            **NATAL_1990,
            pd_method=method,
            pd_type=0,
            pd_direction_mode="zodiacal",
            pd_time_key="Naibod",
        )
        assert "error" not in direct_res, method
        pd = direct_res["primary_directions"]
        assert pd["method"] == method
        assert "calculation_basis" not in direct_res["natal_reference"]
        converse_res = calculate_timing_tool(
            tool_name="primary_directions",
            **NATAL_1990,
            pd_method=method,
            pd_type=1,
            pd_direction_mode="zodiacal",
            pd_time_key="Naibod",
        )
        assert "error" not in converse_res, method
        sigs = {
            ev.get("significator")
            for ev in pd.get("timeline", pd.get("directions", []))
        }
        assert any(
            p in sigs for p in ("Sun", "Moon", "Fortune", "Ascendant", "Medium_Coeli")
        )

    # Circumpolar latitude must degrade gracefully without crashing
    polar_pd = calculate_timing_tool(
        tool_name="primary_directions",
        **{**NATAL_1990, "birth_latitude": 70.0},
        pd_method="placidus",
        high_latitude_fallback="porphyry",
    )
    assert "error" not in polar_pd


def test_zodiacal_releasing_l4_eros_and_chiron_return_bounds() -> None:
    zr = calculate_timing_tool(
        tool_name="zodiacal_releasing",
        **NATAL_1990,
        analysis_year=2025,
        analysis_month=5,
        analysis_day=17,
    )
    assert "error" not in zr
    eros = zr["zodiacal_releasing"]["eros"]
    assert eros["current_level_4"] is not None
    assert len(eros["level_4_timeline"]) > 0
    assert zr["zodiacal_releasing"]["calculation_basis"]["published_levels"] == [
        1,
        2,
        3,
        4,
    ]

    ret = calculate_extrareturns(
        **NATAL_1990,
        analysis_year=2025,
        analysis_month=1,
        analysis_day=1,
    )
    assert "error" not in ret
    chiron = next(r for r in ret["extrareturns"]["returns"] if r["body"] == "Chiron")
    if chiron.get("status") != "unavailable":
        assert chiron["most_recent_return"] is None
        assert chiron["next_return"] is not None


def test_horary_election_hamburg_and_relationship_features_and_no_prose_bloat() -> None:
    horary = calculate_horary(
        question_year=2025,
        question_month=3,
        question_day=15,
        question_hour=10,
        question_minute=15,
        timezone_name="Asia/Shanghai",
        longitude=116.4,
        latitude=39.9,
        category="marriage",
        turned_from_house=5,
    )
    assert "error" not in horary
    h = horary["horary"]
    assert h["quesited_house"] == 11
    assert h["perfection"]["status"] != "source_conditions_incomplete"
    assert not (_walk_keys(horary) & PROSE_KEYS)

    elec = calculate_election(
        candidate_year=2025,
        candidate_month=3,
        candidate_day=15,
        candidate_hour=10,
        candidate_minute=15,
        timezone_name="Asia/Shanghai",
        longitude=116.4,
        latitude=39.9,
        topic_id="marriage",
        search_window_hours=12,
    )
    assert "error" not in elec
    assert elec["election"]["planetary_hour"] is not None
    assert elec["election"].get("candidate_windows")
    assert not (_walk_keys(elec) & PROSE_KEYS)

    hamburg = calculate_germany_chart_analysis(
        **NATAL_1990,
        dial_degrees="22.5",
        sensitive_point_query="Sun+Moon-Ascendant",
    )
    assert "error" not in hamburg
    assert "22.5" in hamburg["midpoint_analysis"]["dials"]
    assert hamburg["midpoint_analysis"].get("sensitive_point_query") is not None
    hamburg_bytes = len(json.dumps(hamburg, ensure_ascii=False).encode())
    assert hamburg_bytes < 80 * 1024, f"Hamburg audit too large: {hamburg_bytes} B"
    assert not (_walk_keys(hamburg) & PROSE_KEYS)

    hamburg_directed = calculate_germany_chart_analysis(
        **NATAL_1990,
        analysis_datetime=datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
    )
    assert "error" not in hamburg_directed
    assert (
        hamburg_directed["midpoint_analysis"]["solar_arc_analysis"]["status"]
        == "computed"
    )
    assert not (_walk_keys(hamburg_directed) & PROSE_KEYS)

    rel = calculate_relative_chart_analysis(
        inner_payload=NATAL_1990,
        outer_payload={
            **NATAL_1990,
            "birth_year": 1992,
            "birth_month": 8,
            "birth_day": 10,
        },
        relative_mode="composite",
        composite_house_method="mc_latitude",
    )
    assert "error" not in rel
    assert rel.get("composite_to_inner_aspects") is not None
    assert rel.get("composite_to_outer_aspects") is not None


def test_warm_latencies_meet_realtime_budgets() -> None:
    cases = [
        (
            "astrology_chart",
            lambda: calculate_core_chart_analysis(**NATAL_1990, chart_variant="chart"),
            150.0,
        ),
        (
            "horary_chart",
            lambda: calculate_horary(
                question_year=2025,
                question_month=3,
                question_day=15,
                question_hour=10,
                question_minute=15,
                timezone_name="Asia/Shanghai",
                longitude=116.4,
                latitude=39.9,
                category="marriage",
            ),
            600.0,
        ),
        (
            "evaluate_election_time",
            lambda: calculate_election(
                candidate_year=2025,
                candidate_month=3,
                candidate_day=15,
                candidate_hour=10,
                candidate_minute=15,
                timezone_name="Asia/Shanghai",
                longitude=116.4,
                latitude=39.9,
                topic_id="marriage",
            ),
            200.0,
        ),
        (
            "planetary_returns",
            lambda: calculate_extrareturns(
                **NATAL_1990, analysis_year=2025, analysis_month=1, analysis_day=1
            ),
            400.0,
        ),
        (
            "hamburg_midpoint_chart",
            lambda: calculate_germany_chart_analysis(**NATAL_1990),
            150.0,
        ),
        (
            "lunar_phase_progressions",
            lambda: calculate_lunation_phase(**NATAL_1990),
            250.0,
        ),
    ]
    for label, fn, limit_ms in cases:
        fn()  # warmup
        best_ms = float("inf")
        for _ in range(2):
            t0 = time.process_time()
            res = fn()
            elapsed_ms = (time.process_time() - t0) * 1000.0
            assert "error" not in res, label
            best_ms = min(best_ms, elapsed_ms)
        assert (
            best_ms < limit_ms
        ), f"{label} took {best_ms:.2f} ms CPU (limit {limit_ms} ms)"
