"""Source-conditioned unique子卯 correction, complete old controls retained."""

import gzip
import hashlib
import importlib.util
import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_source_annotations import SourceCurrentCalculation
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate, evaluate_strength_policy
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from tests.bazi_refactor_reference import assessment_baseline, exact_digest

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_single_end_resolution_v1"
D = ROOT / "docs/validation/bazi-single-end-resolution-files-v1"
ORDER = ("year", "month", "day", "hour")


def chart(values):
    return dict(zip(ORDER, map(tuple, values)))


def test_new_v10_true_single_end_receipt_valid():
    value = calculate_bazi_source_compare("乙丑", "戊子", "丙辰", "辛卯")[
        "current_calculation"
    ]
    assert value["method_id"] == "season_root_revelation_relations_v10"
    SourceCurrentCalculation.model_validate(value)


def test_v9_false_resolution_still_rejected():
    events = json.loads(
        (
            ROOT
            / "docs/validation/bazi-punishment-resolution-files-v1/all20736-discovery-first.json"
        ).read_text()
    )["bad"][0]["relations"]
    with pytest.raises(ValidationError):
        SourceCurrentCalculation.model_validate(
            {
                "method_id": "season_root_revelation_relations_v9",
                "assessment": {"relations": events},
            }
        )


def test_new_v10_natal_evidence_valid():
    p = chart(["乙丑", "戊子", "丙辰", "辛卯"])
    BaziEvidenceChain.model_validate(
        build_natal_evidence(p, ElementAnalysis.analyze_day_master_strength(p))
    )


def test_all20736_relation_decisions_equal_pre_edit_reference_and_v9_replays():
    count = changed = 0
    for line in gzip.open(D / "all20736-geometry-first.jsonl.gz", "rt"):
        row = json.loads(line)
        p = dict(zip(ORDER, (("甲", b) for b in row["branches"])))
        phase = ElementAnalysis.seasonal_phases(p["month"][1])
        result = evaluate_strength_policy(p, phase, DEFAULT_POLICY)
        prior = _evaluate(
            p,
            phase,
            DEFAULT_POLICY,
            stem_effect_mode="precise_binding_only_v1",
            formation_overlap_policy="complete_same_target_affiliation_v1",
            punishment_resolution_policy="completed_combination_punishment_resolution_v1",
        )
        assert result["relations"] == row["after"]
        assert prior["relations"] == row["before"]
        changed += result["relations"] != prior["relations"]
        count += 1
    assert (count, changed) == (20736, 300)


def test_all3000_probe_values_equal_first_candidate_and_independent_exact_arithmetic():
    path = (
        ROOT / "tests/fixtures/bazi_strength_threshold_v1/independent_reference_v2.py"
    )
    spec = importlib.util.spec_from_file_location("single_end_independent", path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    rows = json.loads(
        gzip.decompress((D / "all-affected-daystems-first.json.gz").read_bytes())
    )["rows"]
    assert len(rows) == 3000
    accepted = assessment_baseline()
    source = D / "all-affected-daystems-first.json.gz"
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == accepted["single_end_source_sha256"]
    )
    for row, expected in zip(rows, accepted["single_end_probes"], strict=True):
        assert row["pillars"] == expected["pillars"]
        p = chart(row["pillars"])
        phase = ElementAnalysis.seasonal_phases(p["month"][1])
        current = evaluate_strength_policy(p, phase, DEFAULT_POLICY)
        prior = _evaluate(
            p,
            phase,
            DEFAULT_POLICY,
            stem_effect_mode="precise_binding_only_v1",
            formation_overlap_policy="complete_same_target_affiliation_v1",
            punishment_resolution_policy="completed_combination_punishment_resolution_v1",
        )
        assert exact_digest(prior) == expected["prior_sha256"]
        assert exact_digest(current) == expected["current_sha256"]
        exact = reference.reconstruct(row["pillars"], current["relations"])
        assert {
            e: Fraction(v)
            for e, v in current["threshold_arithmetic"]["energies_exact"].items()
        } == exact["energies"]


@pytest.mark.parametrize(
    "fault", ["missed_resolution", "repeated_pair", "invented_cover"]
)
def test_known_v10_conditions_reject_wrong_state_even_without_inventory(fault):
    current = calculate_bazi_source_compare("乙丑", "戊子", "丙辰", "辛卯")[
        "current_calculation"
    ]
    current.pop("branch_combination_candidates")
    assessment = current["assessment"]
    event = next(e for e in assessment["relations"] if e["kind"] == "刑")
    if fault == "missed_resolution":
        event["status"] = "active"
    elif fault == "repeated_pair":
        for root in assessment["hidden_stem_ledger"]:
            if root["pillar"] == "day":
                root["branch"] = "卯"
    else:
        for relation in assessment["relations"]:
            if relation["kind"] in {"三会", "三合", "六合"}:
                relation["status"] = "contested_or_clashed"
    with pytest.raises(ValidationError):
        SourceCurrentCalculation.model_validate(current)


def test_partial_branches_and_potential_unknown_cover_not_filled_or_reclassified():
    current = calculate_bazi_source_compare("乙丑", "戊子", "丙辰", "辛卯")[
        "current_calculation"
    ]
    cases = [
        {
            "method_id": current["method_id"],
            "assessment": {"relations": current["assessment"]["relations"]},
        },
        {
            "method_id": current["method_id"],
            "assessment": {
                "relations": [*current["assessment"]["relations"], {"kind": "六合"}]
            },
        },
    ]
    for value in cases:
        assert (
            SourceCurrentCalculation.model_validate(value).model_dump(
                exclude_unset=True
            )
            == value
        )
