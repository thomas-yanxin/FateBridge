"""Punishment cannot be resolved by a combination which was not completed."""

import gzip
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate, evaluate_strength_policy
from tests.fixtures.bazi_punishment_resolution_v1.literal_reference_corrected import (
    GEOMETRIES,
    ORDER,
    corrected_relations,
    remaining_masses,
)

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/validation/bazi-punishment-resolution-files-v1"


@pytest.mark.parametrize("branches", GEOMETRIES)
def test_eight_first_patterns_cannot_resolve_punishment_with_contested_pairs(branches):
    chart = dict(zip(ORDER, (("甲", b) for b in branches)))
    value = evaluate_strength_policy(
        chart, ElementAnalysis.seasonal_phases(chart["month"][1]), DEFAULT_POLICY
    )
    punishment = next(e for e in value["relations"] if e["kind"] == "刑")
    assert punishment["status"] == "active"
    assert all(
        e["status"] == "contested_or_clashed"
        for e in value["relations"]
        if e["kind"] == "六合"
    )


def test_all20736_relations_only_change_eight_unsupported_punishment_statuses():
    count = changed = supported = 0
    old = (
        ROOT
        / "docs/validation/bazi-branch-inventory-files-v1/all20736-stage-before-first.jsonl.gz"
    )
    for line in gzip.open(old, "rt"):
        row = json.loads(line)
        chart = dict(zip(ORDER, (("甲", b) for b in row["branches"])))
        # Replay the explicitly retained v9 policy; current v10 has its own
        # independent all20736 relation gate, including all300 changed cases.
        value = _evaluate(
            chart,
            ElementAnalysis.seasonal_phases(chart["month"][1]),
            DEFAULT_POLICY,
            stem_effect_mode="precise_binding_only_v1",
            formation_overlap_policy="complete_same_target_affiliation_v1",
            punishment_resolution_policy="completed_combination_punishment_resolution_v1",
        )
        expected = corrected_relations(row["relations"])
        assert value["relations"] == expected
        changed += expected != row["relations"]
        supported += sum(
            e["kind"] == "刑" and e["status"] == "resolved_by_combination"
            for e in expected
        )
        count += 1
    assert (count, changed, supported) == (20736, 8, 8)


def test_all5000_default_arithmetic_unchanged_and_more_severe_diagnostic_uses_actual_punishment():
    count, diagnostic_changed = 0, 0
    for line in gzip.open(D / "all5000-before-first.jsonl.gz", "rt"):
        row = json.loads(line)
        chart = dict(zip(ORDER, map(tuple, row["pillars"])))
        phases = ElementAnalysis.seasonal_phases(chart["month"][1])
        for field, coefficient in (
            ("default", Fraction(9, 10)),
            ("diagnostic", Fraction(4, 5)),
        ):
            policy = (
                DEFAULT_POLICY
                if field == "default"
                else replace(DEFAULT_POLICY, punishment=0.8)
            )
            result = evaluate_strength_policy(chart, phases, policy)
            if field == "default":
                signature = {
                    k: v
                    for k, v in result.items()
                    if k not in {"relations", "punishment_resolution_policy"}
                }
                assert json.dumps(signature, sort_keys=True) == json.dumps(
                    row["default_signature"], sort_keys=True
                )
            masses = remaining_masses([p[1] for p in row["pillars"]], coefficient)
            for root in result["hidden_stem_ledger"]:
                assert root["remaining_mass"] == pytest.approx(
                    float(masses[root["pillar"], root["stem"]]), abs=1e-12, rel=0
                )
            if field == "diagnostic":
                diagnostic_changed += (
                    result["hidden_stem_ledger"]
                    != row["diagnostic_signature"]["hidden_stem_ledger"]
                )
        count += 1
    assert count == diagnostic_changed == 5000


@pytest.mark.parametrize(
    "kind",
    [
        "source_without_inventory",
        "natal_without_inventory",
        "wrong_policy",
        "unknown_unrelated_positions",
    ],
)
def test_v9_known_false_resolution_cannot_hide_behind_partial_facts(kind):
    from pydantic import ValidationError

    from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
    from fatebridge.core.output_source_annotations import SourceCurrentCalculation

    raw = json.loads((D / "all20736-discovery-first.json").read_text())["bad"][0][
        "relations"
    ]
    if kind == "wrong_policy":
        value = {
            "method_id": "season_root_revelation_relations_v9",
            "assessment": {
                "punishment_resolution_policy": "initial_candidate_protection_v1"
            },
        }
        with pytest.raises(ValidationError):
            SourceCurrentCalculation.model_validate(value)
    elif kind in {"source_without_inventory", "unknown_unrelated_positions"}:
        if kind == "unknown_unrelated_positions":
            raw = [*raw, {"kind": "自刑"}]
        with pytest.raises(ValidationError):
            SourceCurrentCalculation.model_validate(
                {
                    "method_id": "season_root_revelation_relations_v9",
                    "assessment": {"relations": raw},
                }
            )
    else:
        value = {
            "strength_context": {"method_id": "season_root_revelation_relations_v9"},
            "classical_passage_relations": {
                "events": [
                    {"id": f"assessment.relations:{i}", "plane": "branch", "receipt": e}
                    for i, e in enumerate(raw)
                ]
            },
        }
        with pytest.raises(ValidationError):
            BaziEvidenceChain.model_validate(value)


def test_old_v8_receipt_remains_replayable_and_unknown_cover_stays_unknown():
    from fatebridge.core.output_source_annotations import SourceCurrentCalculation

    raw = json.loads((D / "all20736-discovery-first.json").read_text())["bad"][0][
        "relations"
    ]
    for method, relations in (
        ("season_root_revelation_relations_v8", raw),
        ("season_root_revelation_relations_v9", [*raw, {"kind": "六合"}]),
    ):
        value = {"method_id": method, "assessment": {"relations": relations}}
        assert (
            SourceCurrentCalculation.model_validate(value).model_dump(
                exclude_unset=True
            )
            == value
        )
