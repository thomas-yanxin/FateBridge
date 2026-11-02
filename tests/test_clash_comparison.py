"""Decision provenance and causal invariance, not classical accuracy scores."""

import copy
import gzip
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.clash_comparison import (
    build_clash_comparison,
    clash_comparison_snapshot_lines,
)
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_clash_comparison import ClashComparison
from fatebridge.core.strength import DEFAULT_POLICY, SOURCES, evaluate_strength_policy
from tests.bazi_refactor_reference import assert_strength_matches_before_repair


def pillars(text):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, text.split())))


def model(text):
    return ElementAnalysis.analyze_day_master_strength(pillars(text))["assessment"]


def test_tender_wood_counterexample_discloses_the_actual_proxy_without_fixing_its_label():
    a = model("丁丑 壬寅 丙申 壬辰")
    trace = a["clash_comparison"]
    assert a["strength_level"] == "中和"  # Unresolved source disagreement.
    row = trace["events"][0]
    assert row["positions"] == ["month", "day"] and row["distance"] == 1
    wood, metal = row["powers"]
    # Hand arithmetic: 木=寅甲16/7+辰乙4/7; 金=丑辛2/7+申庚8/7.
    assert wood["raw_budget"] == pytest.approx(20 / 7)
    assert metal["raw_budget"] == pytest.approx(10 / 7)
    assert row["applied_root_retention"] == {"month": 0.9, "day": 0.5}
    assert trace["resource_stage"] == "before_interactions"
    assert "indirect_generation" in trace["not_included_factors"]
    assert "thermal_receiving_capacity" in trace["not_included_factors"]
    assert trace["classical_effective_force"] == "not_adjudicated"
    ClashComparison.model_validate(trace)


def test_trace_and_snapshot_reuse_the_same_receipt_and_do_not_recompute():
    p = pillars("丁丑 壬寅 丙申 壬辰")
    strength = ElementAnalysis.analyze_day_master_strength(p)
    receipt = strength["assessment"]["clash_comparison"]
    shared = build_natal_evidence(p, strength)["strength_context"]["clash_comparison"]
    assert shared == receipt
    shared["events"][0]["powers"][0]["raw_budget"] = 123
    assert receipt["events"][0]["powers"][0]["raw_budget"] != 123
    assert any(
        "123.000000" in line
        for line in clash_comparison_snapshot_lines({"clash_comparison": shared})
    )
    assert build_natal_evidence(p)["strength_context"]["clash_comparison"] is None


@pytest.mark.parametrize(
    "text,branch",
    [
        ("壬子 己丑 丙午 乙酉", "combination_resolution"),
        ("甲辰 戊戌 丙子 辛酉", "storage_movement"),
    ],
)
def test_non_power_branches_never_fabricate_a_winning_budget(text, branch):
    a = model(text)
    row = next(
        r for r in a["clash_comparison"]["events"] if r["calculation_branch"] == branch
    )
    assert row["powers"] is None and row["applied_root_retention"] is None
    ClashComparison.model_validate(a["clash_comparison"])


def test_legacy_and_no_clash_have_different_missingness_without_backfilling():
    p = pillars("丁丑 壬寅 丙申 壬辰")
    old = {
        "kind": "六冲",
        "positions": ["month", "day"],
        "status": "active",
        "source_id": "ditian_branch",
        "root_multipliers": {"month": 0.9, "day": 0.5},
    }
    trace = build_clash_comparison(p, [old], SOURCES)
    assert trace["events"][0]["calculation_branch"] == "legacy_power_unavailable"
    assert trace["events"][0]["powers"] is None
    assert "不补算" in "".join(
        clash_comparison_snapshot_lines({"clash_comparison": trace})
    )
    empty = model("甲寅 乙卯 丙辰 丁未")["clash_comparison"]
    assert empty["events"] == []
    ClashComparison.model_validate(trace)
    ClashComparison.model_validate({"classical_effective_force": "not_adjudicated"})


@pytest.mark.parametrize(
    "damage",
    ["total", "double", "imaginary_root", "position", "branch_mode", "authority"],
)
def test_contract_rejects_fabricated_calculation_facts(damage):
    trace = copy.deepcopy(model("丁丑 壬寅 丙申 壬辰")["clash_comparison"])
    row = trace["events"][0]
    if damage == "total":
        row["powers"][0]["raw_budget"] = 999
    elif damage == "double":
        row["powers"][0]["contributors"].append(row["powers"][0]["contributors"][0])
    elif damage == "imaginary_root":
        row["powers"][0]["contributors"][0]["stem"] = "丁"
    elif damage == "position":
        row["distance"] = 3
    elif damage == "branch_mode":
        row["calculation_branch"] = "combination_resolution"
    else:
        trace["classical_effective_force"] = "verified"
    with pytest.raises(ValidationError):
        ClashComparison.model_validate(trace)


def test_parameters_not_used_in_the_proxy_do_not_silently_enter_its_explanation():
    p = pillars("丁丑 壬寅 丙申 壬辰")
    phases = ElementAnalysis.seasonal_phases(p["month"][1])
    values = []
    for policy in [
        DEFAULT_POLICY,
        replace(DEFAULT_POLICY, seasonal_spread=0, reveal_multiplier=1),
    ]:
        a = evaluate_strength_policy(p, phases, policy)
        values.append(
            next(e["power_comparison"] for e in a["relations"] if e["kind"] == "六冲")
        )
    assert values[0] == values[1]


def test_all_retained_inputs_keep_the_complete_prior_calculation_after_removing_only_new_trace():
    folder = Path(__file__).parent / "fixtures/bazi_clash_trace_v1"
    raw = (folder / "before.json.gz").read_bytes()
    manifest = json.loads((folder / "manifest.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest["baseline_sha256"]
    before = json.loads(gzip.decompress(raw))
    assert before["distinct_inputs"] == 228
    for case in before["rows"]:
        p = dict(zip(("year", "month", "day", "hour"), map(tuple, case["pillars"])))
        after = ElementAnalysis.analyze_day_master_strength(p)
        ClashComparison.model_validate(after["assessment"]["clash_comparison"])
        assert_strength_matches_before_repair(case["pillars"], after)
