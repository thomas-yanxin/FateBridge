"""Conditional war evidence through real transports and birth-time sampling."""

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_balas import directional_strength
from fatebridge.core.jyotish_kala import temporal_balas
from fatebridge.core.jyotish_sthana import calculate_sthana
from fatebridge.core.jyotish_war import SOURCE
from tests.test_jyotish_kala import packet
from tests.test_jyotish_transports import call_surfaces

PAYLOAD = dict(
    birth_year=2023,
    birth_month=3,
    birth_day=2,
    birth_hour=0,
    birth_timezone="UTC",
    birth_latitude=0,
    birth_longitude=0,
)


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_real_two_disjoint_pairs_keep_conditional_values_and_source_across_surfaces(
    monkeypatch, capsys, key
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        PAYLOAD,
        [
            "india.strengths.kala_bala",
            "india.strengths.shadbala_assessment",
            "india.topic_evidence",
            "india.rulesets",
            "india.rule_trace",
        ],
    )
    india = result["india"]
    kala = india["strengths"]["kala_bala"]
    war = kala["components"]["yuddha_bala"]
    assert [r["planets"] for r in war["candidates"]] == [
        ["Mercury", "Saturn"],
        ["Jupiter", "Venus"],
    ]
    assert war["summary"]["Mercury"] is war["summary"]["Saturn"] is None
    assert "yuddha_bala" not in kala["missing_components"]
    assert kala["status"] == "conditional_nature_results"
    assert war["unresolved_planets"] == []
    assert war["conditional_planets"] == ["Mercury", "Saturn"]
    assert war["summary"]["Jupiter"] < 0 and war["summary"]["Venus"] > 0
    assert war["summary"]["Jupiter"] == -war["summary"]["Venus"]
    assert india["strengths"]["shadbala_assessment"]["total_virupa"] is None
    assert SOURCE["id"] in {s["id"] for s in india["rulesets"]}
    assert "jyotish.yuddha_raman_76_77.v1" in {
        r["rule_id"] for r in india["rule_trace"]
    }
    assert "not a complete Raman" in war["upstream_profile"]["scope"]
    for name, values in war["scenarios"].items():
        assert values["Mercury"] == -values["Saturn"]
        assert values["Jupiter"] == -values["Venus"]
        assert sum(values.values()) == pytest.approx(0, abs=1e-10)
        for p in values:
            parts = [
                (
                    component["scenarios"][name][p]
                    if comp in {"paksha_bala", "yuddha_bala"}
                    else component["summary"][p]
                )
                for comp, component in kala["components"].items()
            ]
            assert kala["scenarios"][name][p] == pytest.approx(sum(parts), abs=1e-10)
    for topic in india["topic_evidence"].values():
        for fact in topic["factors"]:
            if fact.get("rule_id") != "jyotish.kala_components.v1":
                continue
            value = {"india": india}
            for token in fact["fact_path"].split("."):
                value = value[token]
            assert fact["fact"] == value
            assert fact["supporting_source_id"] == SOURCE["id"]


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_nested_single_pair_arithmetic_evidence_is_not_lost_in_projection(
    monkeypatch, capsys, key
):
    path = "india.strengths.kala_bala.components.yuddha_bala.evidence"
    result = call_surfaces(monkeypatch, capsys, key, PAYLOAD, [path])
    evidence = result["india"]["strengths"]["kala_bala"]["components"]["yuddha_bala"][
        "evidence"
    ]
    assert evidence
    assert all(
        row["pairs"][1]["fixed_disc_difference_arcseconds"] == 173.8
        for row in evidence.values()
    )
    assert all(
        row["prewar_basis"]["Mercury"]["inputs"]["dig_bala"] is not None
        for row in evidence.values()
    )


def test_same_branch_war_and_paksha_do_not_poison_all_kala_scenarios_with_consensus_null():
    birth = build_astro_birth_info(**PAYLOAD)
    raw = positions(birth)
    result = temporal_balas(
        raw,
        packet(raw["julian_day_ut"] - 0.25),
        0,
        sthana=calculate_sthana(raw),
        dig=directional_strength(raw),
    )
    kala = result["kala_bala"]
    war = kala["components"]["yuddha_bala"]
    assert war["summary"]["Mercury"] is None
    assert kala["summary"]["Mercury"] is None
    assert all(row["Mercury"] is not None for row in kala["scenarios"].values())
    for name, row in kala["scenarios"].items():
        pair = war["evidence"][name]["pairs"][0]
        expected = pair["amount_virupa"]
        assert abs(war["scenarios"][name]["Mercury"]) == expected


def test_actual_sky_pair_entry_is_retained_on_same_birth_uncertainty_grid():
    payload = {
        **PAYLOAD,
        "birth_month": 3,
        "birth_day": 1,
        "birth_hour": 23,
        "birth_minute": 18,
    }
    birth = build_astro_birth_info(**payload)
    result = build_india(birth, divisions=[], birth_time_uncertainty_minutes=2)
    sensitivity = result["birth_time_sensitivity"]
    states = sensitivity["yuddha_states_on_grid"]
    assert sensitivity["status"] == "changes_detected"
    assert len(states) == 2
    assert {len(s) for s in states} == {1, 2}
    assert all(any(p["planets"] == ["Jupiter", "Venus"] for p in s) for s in states)
    ranges = sensitivity["temporal_bala_scenario_sample_ranges"]["yuddha_bala"]
    assert all(
        p["sample_count"] == sensitivity["sample_count"]
        for branch in ranges.values()
        for p in branch.values()
    )
    assert any(
        branch["Mercury"]["minimum"] != branch["Mercury"]["maximum"]
        for branch in ranges.values()
    )
