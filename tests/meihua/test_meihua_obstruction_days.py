"""Frozen source day counts; reused geometry is not real prediction evidence."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.meihua_obstruction_days import build_obstruction_timing
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_obstruction_days_v1"
CASES = json.loads((FIXTURE / "expected384.json").read_bytes())["cases"]
MANUAL = json.loads((FIXTURE / "candidate-manual.json").read_bytes())


def at(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def layer(out):
    return out["interpretation"]["stage_emphasis"]["obstruction_timing"]


def assert_null_forecast(value):
    for key in [
        "selected_single_delay",
        "net_effective_delay",
        "calendar_anchor",
        "inclusive_counting_convention",
        "event_time",
        "real_outcome",
    ]:
        assert value[key] is None
    assert not value["multiple_role_delays_summed"]
    assert value["independent_verified_observations"] == 0


def test_preimplementation_reference_and_explicit_versus_analogy_scope():
    m = json.loads((FIXTURE / "manifest.json").read_bytes())
    assert not m["implementation_present_at_reference_freeze"]
    assert m["geometry_reused"] == 384
    assert m["eligible_reused_geometry"] == 86
    assert m["new_literal_day_examples"] == 2
    assert m["source_analogy_day_counts"] == 6
    for name, expected in m["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['code']}-{c['line']}")
def test_all_384_reused_geometries_under_three_declared_scenario_states(case):
    for scenario in [None, "favorable_matter", "unfavorable_matter"]:
        out = calculate_meihua_cast(
            casting={
                "method": "existing",
                "hexagram_code": case["code"],
                "moving_line": case["line"],
            },
            matter_scenario=scenario,
        )
        assert "error" not in out
        value = layer(out)
        assert value["original_body"]["trigram"] == case["body"]
        assert at(out, value["original_body"]["fact_path"])["name"] == case["body"]
        assert value["generation_roles"] == case["generation_roles"]
        assert value["structural_condition_met"] is case["structural_condition_met"]
        assert value["selected_clause_applies"] is (
            False
            if scenario is None and not case["structural_condition_met"]
            else case["conditions"][scenario or "not_collected"]
        )
        actual = value["attacker_records"]
        assert [
            {
                "role": r["role"],
                "trigram": r["trigram"],
                "days": r["nominal_source_day_count"],
                "basis": r["day_count_basis"],
            }
            for r in actual
        ] == case["attackers"]
        for record in actual:
            assert at(out, record["fact_path"])["name"] == record["trigram"]
            assert at(out, record["relation_fact_path"]) == "用克体"
            assert (
                at(out, record["countercontrol_fact_path"])
                == record["countercontrol_qualification"]
            )
            assert record["applied_source_day_count"] == (
                record["nominal_source_day_count"]
                if value["selected_clause_applies"] is True
                else None
            )
            assert record["net_effective_delay"] is None
        candidates = value["distinct_trigram_day_candidates"]
        assert len(candidates) == len({r["trigram"] for r in actual})
        assert sum(len(g["roles"]) for g in candidates) == len(actual)
        assert value["activated_day_candidates"] == (
            candidates if value["selected_clause_applies"] is True else []
        )
        assert bool(value["summary"]) is (value["selected_clause_applies"] is True)
        if value["summary"]:
            assert value["summary"] in out["interpretation"]["comprehensive_judgement"]
        assert_null_forecast(value)


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
def test_manual_count_candidates_do_not_share_timing_or_multiply_duplicate_trigrams(
    basis,
):
    out = calculate_meihua_cast(
        casting={**MANUAL["inputs"], "line_sum_basis": basis},
        matter_scenario="favorable_matter",
    )
    readings = out["interpretation"]["casting_readings"]
    assert readings[0]["line_sum_basis"] == basis
    assert {r["line_sum_basis"] for r in readings} == {"raw_counts", "trigram_numbers"}
    for expected in MANUAL["candidates"]:
        reading = next(
            r for r in readings if r["line_sum_basis"] == expected["line_sum_basis"]
        )
        value = reading["stage_emphasis"]["obstruction_timing"]
        assert reading["line_sum_basis"] == expected["line_sum_basis"]
        assert value["generation_roles"] == expected["generation_roles"]
        assert value["selected_clause_applies"] is expected["applies_under_favorable"]
        assert [
            {
                "role": r["role"],
                "trigram": r["trigram"],
                "days": r["nominal_source_day_count"],
            }
            for r in value["attacker_records"]
        ] == expected["attackers"]
        assert len(value["distinct_trigram_day_candidates"]) == 2
        for record in value["attacker_records"]:
            assert at(out, record["fact_path"])["name"] == record["trigram"]
            assert at(out, record["relation_fact_path"]) == record["relation"]
            assert (
                at(out, record["countercontrol_fact_path"])
                == record["countercontrol_qualification"]
            )
        assert at(out, value["scenario_fact_path"]) == "favorable_matter"
    selected = next(
        r
        for r in out["interpretation"]["casting_readings"]
        if r["line_sum_basis"] == basis
    )
    assert (
        layer(out)["selected_clause_applies"]
        is selected["stage_emphasis"]["obstruction_timing"]["selected_clause_applies"]
    )


@pytest.mark.parametrize(
    "topic",
    ["general", "planning", "reputation", "wealth", "transaction", "travel", "meeting"],
)
def test_topic_and_question_cannot_supply_missing_scenario(topic):
    case = next(c for c in CASES if c["structural_condition_met"])
    out = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic=topic,
        question="我希望一日后成功，求吉事几天完成",
    )
    assert layer(out)["selected_clause_applies"] is None
    assert layer(out)["activated_day_candidates"] == []
    assert layer(out)["scenario_fact_path"] is None


@pytest.mark.parametrize("scenario", [None, "favorable_matter", "unfavorable_matter"])
def test_civil_clock_and_day_qi_are_retained_without_inventing_a_delay_anchor(scenario):
    out = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=26,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        matter_scenario=scenario,
    )
    assert "error" not in out
    value = layer(out)
    if scenario is not None:
        assert at(out, value["scenario_fact_path"]) == scenario
    assert out["interpretation"]["day_qi"] is not None
    assert_null_forecast(value)


def test_weather_does_not_acquire_human_body_timing():
    out = calculate_meihua_cast(
        casting=MANUAL["inputs"], interpretation_topic="weather"
    )
    assert out["interpretation"]["stage_emphasis"] is None


@pytest.mark.parametrize(
    "fault", ["body", "element", "relation", "path", "roles", "qualification"]
)
def test_source_timing_rejects_misbound_calculation_facts(fault):
    out = calculate_meihua_cast(casting=MANUAL["inputs"])
    stages = copy.deepcopy(out["meihua"]["stage_relations"])
    control = copy.deepcopy(out["interpretation"]["internal_countercontrol"])
    if fault == "body":
        stages[0]["body"] = "坎"
    elif fault == "element":
        stages[0]["element"] = "火"
    elif fault == "relation":
        stages[0]["relation"] = "用生体"
    elif fault == "path":
        stages[0]["fact_path"] = "wrong.use_trigram"
    elif fault == "roles":
        stages.reverse()
    else:
        control["qualifications"][0]["target_fact_path"] = "wrong.use_trigram"
    with pytest.raises(ValueError):
        build_obstruction_timing(
            stages,
            control,
            fact_prefix="meihua",
            interpretation_prefix="interpretation",
            matter_scenario="favorable_matter",
            scenario_fact_path="input_normalized.matter_scenario",
        )
