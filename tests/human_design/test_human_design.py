"""Human Design mechanics, PHS/Environment/Cognition, Cross, Composite, Transit, and Oracle tests."""

import json
import subprocess
import time

import pytest

from fatebridge.core.human_design import depth, mechanics
from fatebridge.services.human_design import (
    calculate_human_design,
    compact_human_design,
)


def test_rave_mandala_exact_boundaries() -> None:
    cases = [
        (302.0, 41, 1, 1, 1, 1),
        (301.9999, 60, 6, 6, 6, 5),
        (307.625, 19, 1, 1, 1, 1),
        (0.0, 25, 2, 6, 2, 2),
    ]
    for lon, gate, line, color, tone, base in cases:
        act = mechanics.longitude_activation(lon)
        assert (act["gate"], act["line"], act["color"], act["tone"], act["base"]) == (
            gate,
            line,
            color,
            tone,
            base,
        )


def test_reference_tables_integrity_in_unit_tests() -> None:
    ref = depth.depth_reference()
    assert len(ref["gates"]) == 64
    for row in ref["gates"]:
        assert len(row["line_polarities"]) == 6
        assert set(row["cross_identifiers"]) == {"right", "juxtaposition", "left"}
    assert len(mechanics.CHANNELS) == 36
    assert len(mechanics.GATE_CENTER) == 64


def test_oracle_1990_05_15_and_new_phs_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_subprocess(*args, **kwargs):
        raise AssertionError("Subprocess spawning is forbidden in Human Design")

    monkeypatch.setattr(subprocess, "Popen", no_subprocess)

    t0 = time.perf_counter()
    res = calculate_human_design(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        node_mode="true",
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert "error" not in res
    assert elapsed_ms < 25.0  # well under target (<10ms warm)

    expected_design_prefix = (
        "1990-02-15T02:19:39"
        if res["calculation_policy"]["ephemeris_model"] == "swieph"
        else "1990-02-15T02:19:40"
    )
    assert res["design_utc"].startswith(expected_design_prefix)
    p_sun = next(a for a in res["activations"]["personality"] if a["body"] == "Sun")
    d_sun = next(a for a in res["activations"]["design"] if a["body"] == "Sun")
    assert (p_sun["longitude"] - d_sun["longitude"]) % 360 == pytest.approx(
        88.0, abs=1e-7
    )
    assert (
        p_sun["gate"],
        p_sun["line"],
        p_sun["color"],
        p_sun["tone"],
        p_sun["base"],
    ) == (23, 6, 4, 4, 5)
    assert (
        d_sun["gate"],
        d_sun["line"],
        d_sun["color"],
        d_sun["tone"],
        d_sun["base"],
    ) == (30, 2, 5, 3, 4)
    assert res["bodygraph"]["type"] == "projector"
    assert res["bodygraph"]["authority"] == "emotional"
    assert res["profile"] == "6/2"
    assert res["bodygraph"]["definition"]["kind"] == "split"
    assert res["incarnation_cross"]["gates"] == [23, 43, 30, 29]
    assert res["incarnation_cross"]["name"] == "Left Angle Cross of Dedication"
    assert res["variables"]["code"] == "PRR DLL"

    # PHS Determination, Environment, Motivation, View, Cognition, Sense
    v = res["variables"]
    assert v["phs_determination"]["color"] == 5
    assert v["phs_determination"]["determination"] == "Sound"
    assert v["phs_determination"]["sub_type"] == "High"
    assert v["environment"]["color"] in range(1, 7)
    assert v["cognition"] == {"tone": 3, "name": "Outer Vision"}
    assert v["sense"] == {"tone": 4, "name": "Meditation"}
    assert v["motivation"]["source_term"] == "Need"

    # No prose leakage
    assert "interpretation" not in res
    assert all("reading" not in row for row in res["depth_evidence"]["line_fixings"])

    compact = compact_human_design(res)
    compact_bytes = len(json.dumps(compact, ensure_ascii=False).encode("utf-8"))
    assert compact_bytes < 6144


def test_composite_transit_cycles_and_sensitivity() -> None:
    res = calculate_human_design(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_time_uncertainty_minutes=5,
        cycle_reference_datetime="2020-01-01T00:00:00Z",
        transit_datetime="2026-06-01T00:00:00Z",
        partner={
            "birth_year": 1992,
            "birth_month": 8,
            "birth_day": 20,
            "birth_hour": 9,
            "birth_minute": 15,
            "birth_timezone": "Asia/Shanghai",
        },
    )
    assert res["time_sensitivity"]["sample_count"] == 21
    assert res["cycle_summary"]["status"] in {"computed_finite_search", "partial"}
    saturn = next(b for b in res["cycle_summary"]["bodies"] if b["body"] == "Saturn")
    assert (
        saturn["status"] == "sampled_search_completed" and saturn["contact_count"] >= 1
    )
    assert "newly_activated_channels" in res["transit_overlay"]
    assert "electromagnetic" in res["composite"]["connection_channels"]
