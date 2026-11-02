"""All geometric candidates survive numeric exclusion without implying effect."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.passage_relations import build_passage_relation_context
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from tests.fixtures.bazi_branch_inventory_v1.literal_geometry import (
    ORDER,
    geometries,
    identifier,
)

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/validation/bazi-branch-inventory-files-v1"
COUNTEREXAMPLES = [
    (["癸酉", "甲子", "丙寅", "甲午"], "bc1:半合:火:day-hour"),
    (["癸酉", "甲子", "丁卯", "乙巳"], "bc1:半合:金:year-hour"),
    (["癸巳", "甲寅", "丙子", "丙申"], "bc1:半合:水:day-hour"),
    (["癸巳", "乙卯", "丙子", "丁酉"], "bc1:半合:金:year-hour"),
]


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


def test_all20736_geometries_and_actual_pre_half_stage_trace_agree():
    from fatebridge.core.branch_candidates import build_branch_combination_candidates
    from fatebridge.core.output_branch_candidates import BranchCombinationCandidates

    count = 0
    for line in gzip.open(D / "all20736-stage-before-first.jsonl.gz", "rt"):
        saved = json.loads(line)
        chart = dict(zip(ORDER, (("甲", b) for b in saved["branches"])))
        assessment = {
            "method_id": "season_root_revelation_relations_v8",
            "relations": saved["relations"],
        }
        before = deepcopy(assessment)
        value = build_branch_combination_candidates(chart, assessment)
        assert value["pre_half_claimed_positions"] == saved["claimed_before_half"]
        assert value["pre_half_clashed_positions"] == saved["clashed_before_half"]
        assert [r["id"] for r in value["candidates"]] == [
            identifier(k, t, p) for k, t, p in geometries(saved["branches"])
        ]
        assert all(
            r["screen_decision"] != "unclassified_unrecorded"
            for r in value["candidates"]
        )
        BranchCombinationCandidates.model_validate(value)
        assert assessment == before
        count += 1
    assert count == 20736


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


def test_legacy_context_without_pillars_keeps_its_existing_shape():
    chart = dict(zip(ORDER, map(tuple, ["甲子", "丙寅", "甲午", "庚申"])))
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    natal = build_natal_evidence(chart, strength)
    legacy = build_passage_relation_context(
        natal["classical_passage"], strength["assessment"]
    )
    assert "branch_combination_candidates" not in legacy
    assert all("potential_branch_candidate_refs" not in n for n in legacy["nodes"])


def test_inventory_is_exactly_additive_and_never_changes_calculation():
    source = (
        ROOT
        / "docs/validation/bazi-month-command-integrity-files-v1/all408-source-final-first.jsonl.gz"
    )
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "81766f95c5e45ba866244d793c1dadcdd1f36470893b2077563da3c4eb8492b8"
    )
    manifest = (
        ROOT / "tests/fixtures/architecture_refactor_v1/bazi408-before-manifest.json"
    )
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "bac00f4517a2357188312ab9c325ba8d051dcc224b8f32aee7bf0b6f453b17d8"
    )
    before = json.loads(manifest.read_bytes())
    saved = [json.loads(line) for line in gzip.open(source, "rt")]
    for row, expected in zip(saved, before, strict=True):
        chart = dict(zip(ORDER, map(tuple, row["case"]["pillars"])))
        strength = ElementAnalysis.analyze_day_master_strength(chart)
        natal = build_natal_evidence(chart, strength)
        for key, value in (
            ("case", row["case"]),
            ("strength", strength),
            ("natal", natal),
        ):
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            assert hashlib.sha256(encoded).hexdigest() == expected[key + "_sha256"]
        context = natal["classical_passage_relations"]
        inventory = context.pop("branch_combination_candidates")
        assert inventory["calculation_effect"] == "none"
        for node in context["nodes"]:
            node.pop("potential_branch_candidate_refs")
        assert context == build_passage_relation_context(
            natal["classical_passage"], strength["assessment"]
        )
    assert len(saved) == len(before) == 408


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
