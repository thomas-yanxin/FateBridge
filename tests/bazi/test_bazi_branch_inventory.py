"""All geometric candidates survive numeric exclusion without implying effect."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import bazi_evidence
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.passage_relations import build_passage_relation_context
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from tests.support.bazi_geometry_reference import (
    ORDER,
    geometries,
    identifier,
)

ROOT = Path(__file__).resolve().parents[2]
COUNTEREXAMPLES = [
    (["癸酉", "甲子", "丙寅", "甲午"], "bc1:半合:火:day-hour"),
    (["癸酉", "甲子", "丁卯", "乙巳"], "bc1:半合:金:year-hour"),
    (["癸巳", "甲寅", "丙子", "丙申"], "bc1:半合:水:day-hour"),
    (["癸巳", "乙卯", "丙子", "丁酉"], "bc1:半合:金:year-hour"),
]


def _with_literal_candidate_additions(chart, without_inventory, inventory):
    """Add the independently listed geometry refs; never remove numeric fields."""
    specs = geometries([chart[p][1] for p in ORDER])
    assert len(inventory["candidates"]) == len(specs)
    for row, (kind, target, positions) in zip(
        inventory["candidates"], specs, strict=True
    ):
        assert row["id"] == identifier(kind, target, positions)
        assert (row["kind"], row["target"], row["positions"]) == (
            kind,
            target,
            list(positions),
        )
    expected = deepcopy(without_inventory)
    expected["branch_combination_candidates"] = inventory
    for node in expected["nodes"]:
        carriers = node["root_carrier_positions"]
        node["potential_branch_candidate_refs"] = (
            [
                identifier(kind, target, positions)
                for kind, target, positions in specs
                if set(carriers) & set(positions)
            ]
            if carriers is not None
            else None
        )
    return expected


@pytest.mark.parametrize("values,identity", COUNTEREXAMPLES)
def test_four_first_counterexamples_expose_suppressed_half_on_both_domain_outputs(
    values, identity
):
    chart = dict(zip(ORDER, map(tuple, values)))
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    natal = build_natal_evidence(chart, strength)
    actual = calculate_bazi_source_compare(*values)
    first = natal["classical_passage_relations"]["branch_combination_candidates"]
    second = actual["current_calculation"]["branch_combination_candidates"]
    assert first == second
    row = next(r for r in first["candidates"] if r["id"] == identity)
    assert row["screen_decision"] == "suppressed_before_half_evaluation"
    assert row["clashed_blockers"] and row["actual_event_refs"] == []
    assert row["current_statuses"] == []
    assert first["calculation_effect"] == "none"
    assert first["effective_combination"] == "not_adjudicated"
    assert not any(e["kind"] == "半合" for e in strength["assessment"]["relations"])
    for node in natal["classical_passage_relations"]["nodes"]:
        carriers = node["root_carrier_positions"]
        if carriers is not None:
            assert (identity in node["potential_branch_candidate_refs"]) == bool(
                set(carriers) & set(row["positions"])
            )


def test_missing_or_unknown_effects_do_not_manufacture_known_empty_screen():
    from fatebridge.core.branch_candidates import build_branch_combination_candidates

    chart = dict(zip(ORDER, map(tuple, ["癸酉", "甲子", "丁卯", "乙巳"])))
    absent = build_branch_combination_candidates(chart, {})
    assert absent["effects_status"] == "not_supplied"
    assert absent["source_relation_count"] is None
    assert absent["pre_half_claimed_positions"] is None
    assert absent["pre_half_clashed_positions"] is None
    assert all(
        r["actual_event_refs"] is None and r["screen_decision"] == "not_assessed"
        for r in absent["candidates"]
    )
    unknown = build_branch_combination_candidates(
        chart, {"method_id": "future", "relations": []}
    )
    assert (
        unknown["effects_status"] == "supplied"
        and unknown["source_relation_count"] == 0
    )
    assert unknown["screen_status"] == "not_identified"
    assert all(
        r["claimed_blockers"] is None and r["clashed_blockers"] is None
        for r in unknown["candidates"]
    )


def test_partial_context_without_pillars_does_not_invent_inventory():
    chart = dict(zip(ORDER, map(tuple, ["甲子", "丙寅", "甲午", "庚申"])))
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    natal = build_natal_evidence(chart, strength)
    partial = build_passage_relation_context(
        natal["classical_passage"], strength["assessment"]
    )
    assert "branch_combination_candidates" not in partial
    assert all("potential_branch_candidate_refs" not in n for n in partial["nodes"])


def test_current408_inventory_is_read_only_and_exactly_additive(monkeypatch):
    from fatebridge.core.branch_candidates import build_branch_combination_candidates

    def without_inventory(passage, assessment, *, pillars=None):
        return build_passage_relation_context(passage, assessment)

    count = 0
    for row in json.loads(
        (ROOT / "tests/data/bazi/arithmetic-inputs.json").read_text()
    ):
        chart = dict(zip(ORDER, map(tuple, row["pillars"])))
        strength = ElementAnalysis.analyze_day_master_strength(chart)
        original = deepcopy({"chart": chart, "strength": strength})
        encoded = json.dumps(
            original,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        inventory = build_branch_combination_candidates(chart, strength["assessment"])
        assert {"chart": chart, "strength": strength} == original
        assert (
            json.dumps(
                {"chart": chart, "strength": strength},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            == encoded
        )
        actual = build_natal_evidence(chart, strength)
        with monkeypatch.context() as local:
            local.setattr(
                bazi_evidence, "build_passage_relation_context", without_inventory
            )
            baseline = build_natal_evidence(chart, strength)
        expected = deepcopy(baseline)
        expected["classical_passage_relations"] = _with_literal_candidate_additions(
            chart, baseline["classical_passage_relations"], inventory
        )
        # Full current natal objects differ only by explicitly reconstructed
        # additions; no old/current numeric field is removed or normalized.
        assert actual == expected
        assert inventory["calculation_effect"] == "none"
        assert inventory["effective_combination"] == "not_adjudicated"
        assert {"chart": chart, "strength": strength} == original
        assert (
            json.dumps(
                {"chart": chart, "strength": strength},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            == encoded
        )
        count += 1
    assert count == 408


def test_known_inventory_contradictions_are_rejected_without_filling_partial_facts():
    from fatebridge.core.branch_candidates import build_branch_combination_candidates
    from fatebridge.core.output_branch_candidates import BranchCombinationCandidates

    chart = dict(zip(ORDER, map(tuple, ["癸酉", "甲子", "丁卯", "乙巳"])))
    value = build_branch_combination_candidates(
        chart, ElementAnalysis.analyze_day_master_strength(chart)["assessment"]
    )
    for fault in ("missing_candidate", "wrong_screen", "fake_effect", "wrong_branch"):
        bad = deepcopy(value)
        if fault == "missing_candidate":
            bad["candidates"].pop()
        elif fault == "wrong_screen":
            bad["candidates"][-1]["clashed_blockers"] = []
        elif fault == "fake_effect":
            bad["calculation_effect"] = "applied"
        else:
            bad["candidates"][-1]["branches"] = ["子", "卯"]
        with pytest.raises(ValidationError):
            BranchCombinationCandidates.model_validate(bad)
    partial = {
        "method_id": value["method_id"],
        "candidates": [{"id": value["candidates"][-1]["id"]}],
    }
    assert (
        BranchCombinationCandidates.model_validate(partial).model_dump(
            exclude_unset=True
        )
        == partial
    )


@pytest.mark.parametrize(
    "fault",
    [
        "invented_ref",
        "invented_status",
        "known_partial_screen",
        "known_partial_carrier",
    ],
)
def test_cross_receipt_contradictions_survive_partial_projection(fault):
    from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
    from fatebridge.core.output_source_annotations import SourceCurrentCalculation

    chart = dict(zip(ORDER, map(tuple, ["癸酉", "甲子", "丁卯", "乙巳"])))
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    natal = build_natal_evidence(chart, strength)
    inventory = natal["classical_passage_relations"]["branch_combination_candidates"]
    if fault in {"invented_ref", "invented_status"}:
        current = {
            "assessment": strength["assessment"],
            "branch_combination_candidates": inventory,
        }
        if fault == "invented_ref":
            inventory["candidates"][-1].update(
                actual_event_refs=["assessment.relations:0"],
                current_statuses=["active"],
                screen_decision="recorded_event",
            )
        else:
            inventory["candidates"][-1]["current_statuses"] = ["active"]
            inventory["candidates"][-1].pop("actual_event_refs")
        with pytest.raises(ValidationError):
            SourceCurrentCalculation.model_validate(current)
    elif fault == "known_partial_screen":
        value = {
            "pre_half_clashed_positions": ["year", "day"],
            "candidates": [
                {
                    "id": "bc1:半合:金:year-hour",
                    "screen_decision": "not_assessed",
                    "actual_event_refs": [],
                }
            ],
            "screen_status": "reconstructed_v8",
        }
        with pytest.raises(ValidationError):
            from fatebridge.core.output_branch_candidates import (
                BranchCombinationCandidates,
            )

            BranchCombinationCandidates.model_validate(value)
    else:
        value = {
            "classical_passage_relations": {
                "branch_combination_candidates": {
                    "branches_by_position": {"month": "子"}
                }
            },
            "classical_passage": {"nodes": [{"id": "month:hidden:癸", "branch": "卯"}]},
        }
        with pytest.raises(ValidationError):
            BaziEvidenceChain.model_validate(value)
