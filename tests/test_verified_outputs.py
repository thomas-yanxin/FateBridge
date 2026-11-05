"""Independent arithmetic vectors, operand tampering, and bound membership."""

from copy import deepcopy
from fractions import Fraction

import mpmath as mp
import pytest

from fatebridge.core.evidence_graph import (
    EvidenceGraph,
    affected_nodes,
    execution_evidence,
)
from fatebridge.core.human_design_apparent_positions import build_context
from fatebridge.core.method_contracts import COMPATIBILITY_INDEX
from fatebridge.core.verified_outputs import (
    collect_source_conflicts,
    collect_verified_outputs,
    verify_output_binding,
)


def budget():
    return {
        "assessment": {
            "support_share": 0.4,
            "threshold_arithmetic": {
                "method_id": "exact_rational_strength_thresholds_v1",
                "day_element": "木",
                "energies_exact": {e: "1" for e in "木火土金水"},
                "support_exact": "2",
                "weaken_exact": "3",
                "share_exact": "2/5",
            },
        }
    }


def test_exact_ratio_error_bound_is_not_a_physical_error_bound():
    data = budget()
    witness = next(
        w
        for w in collect_verified_outputs(data)
        if w.output_path == "/assessment/support_share"
    )
    assert witness.reference_interval_exact == ("2/5", "2/5")
    exact_error = Fraction(2, 5) - Fraction(0.4)
    assert tuple(map(Fraction, witness.reference_minus_reported_interval_exact)) == (
        exact_error,
        exact_error,
    )
    assert not witness.physical_accuracy_certified
    assert witness.upstream_dependency_proof == "not_established"
    verify_output_binding(witness, data)
    changed = deepcopy(data)
    changed["assessment"]["threshold_arithmetic"]["energies_exact"]["木"] = "2"
    with pytest.raises(ValueError, match="操作数"):
        verify_output_binding(witness, changed)


def test_internally_contradictory_exact_receipt_fails_closed():
    data = budget()
    data["assessment"]["threshold_arithmetic"]["share_exact"] = "1/2"
    with pytest.raises(RuntimeError, match="完整操作数矛盾"):
        collect_verified_outputs(data)


def test_original_taiyi_volume2_integer_example_and_missing_term():
    data = {
        "taiyi": {
            "core_board": {
                "main_count": 16,
                "count_trace": {
                    "main": {
                        "count": 16,
                        "counting_rule": "数至太乙宫前",
                        "terminal_palace": "巽",
                        "path": [{"value": v} for v in (1, 8, 3, 4)],
                    }
                },
            }
        }
    }
    witnesses = collect_verified_outputs(data)
    count = next(
        w for w in witnesses if w.output_path == "/taiyi/core_board/main_count"
    )
    assert count.reference_interval_exact == ("16", "16")
    assert len(count.operands) == 4
    assert count.reference_minus_reported_interval_exact == ("0", "0")
    changed = deepcopy(data)
    changed["taiyi"]["core_board"]["count_trace"]["main"]["path"].pop()
    with pytest.raises(RuntimeError):
        collect_verified_outputs(changed)


def test_taiyi_correct_sum_with_wrong_ring_position_is_rejected():
    data = {
        "alignment": {
            "source_marker": "亥",
            "source_position_recount": {
                "count": 16,
                "counting_rule": "数至太乙宫前",
                "terminal_palace": "巽",
                "path": [
                    {"palace": p, "value": v} for p, v in zip("亥子艮卯", (1, 8, 3, 4))
                ],
            },
        }
    }
    proofs = collect_verified_outputs(data)
    ring = next(p for p in proofs if p.method_id == "taiyi_recorded_ring_walk_v1")
    assert ring.reference_interval_exact == ("16", "16")
    assert [p.path for p in ring.operands] == [
        "/alignment/source_marker",
        "/alignment/source_position_recount/terminal_palace",
    ]
    data["alignment"]["source_position_recount"]["path"][2]["palace"] = "乾"
    with pytest.raises(RuntimeError, match="完整环路"):
        collect_verified_outputs(data)


def test_qimen_nine_palace_wrap_is_a_discrete_result_not_a_confidence_score():
    data = {
        "qimen": {
            "rule_trace": [
                {
                    "rule_id": "leaders",
                    "inputs": {"time_ganzhi": "癸亥"},
                    "outputs": {
                        "source_gong": "坎",
                        "dun_type": "阳",
                        "raw_door_gong": "坎",
                    },
                }
            ]
        }
    }
    witnesses = collect_verified_outputs(data)
    assert len(witnesses) == 1 and witnesses[0].discrete_value == "坎"
    assert witnesses[0].unit == "categorical"
    assert witnesses[0].reference_minus_reported_interval_exact is None
    data["qimen"]["rule_trace"][0]["outputs"]["raw_door_gong"] = "坤"
    with pytest.raises(RuntimeError, match="九宫运算"):
        collect_verified_outputs(data)


def test_proven_operand_edges_invalidate_the_derived_ratio():
    data = budget()
    value = execution_evidence((COMPATIBILITY_INDEX,), {}, data, "origin")
    graph = EvidenceGraph.model_validate(value["graph"])
    start = "operand:/assessment/threshold_arithmetic/energies_exact/木"
    target = "math:exact_component_support_relation_v1:/assessment/support_share"
    assert target in affected_nodes(graph, {start})
    assert value["coverage"]["semantic_dependency_proof_complete"] is False
    assert value["error_budget"]["output_error_bounds"] is None
    assert value["error_budget"]["conditional_output_bounds"]


def test_nominal_solar_geometry_enclosures_contain_independent_high_precision_values():
    # One degree on the equator; an independent arbitrary precision formula,
    # using literal nominal constants, not the production interval routines.
    context = build_context(
        [
            {
                "batch_id": "test",
                "observed_count": 1,
                "bodies": [
                    {
                        "body": "Sun",
                        "native_coordinates": [0.0, 0.0, 1.0, 0.0],
                        "return_flags": 258,
                    },
                    {
                        "body": "Uranus",
                        "native_coordinates": [1.0, 0.0, 2.0, 0.0],
                        "return_flags": 258,
                    },
                ],
            }
        ],
        {},
    )
    witnesses = collect_verified_outputs({"context": context})
    assert len(witnesses) == 3
    with mp.workdps(100):
        expected = {
            "separation_radians": mp.pi / 180,
            "nominal_solar_radius_radians": mp.asin(mp.mpf(695700000) / 149597870700),
        }
        expected["projection_margin_radians"] = (
            expected["separation_radians"] - expected["nominal_solar_radius_radians"]
        )
        for w in witnesses:
            low, high = map(Fraction, w.reference_interval_exact)
            left = mp.mpf(low.numerator) / low.denominator
            right = mp.mpf(high.numerator) / high.denominator
            assert left <= expected[w.output_path.rsplit("/", 1)[1]] <= right
            assert not w.physical_accuracy_certified
            verify_output_binding(w, {"context": context})


def test_source_contradiction_preserves_both_sides_without_adjudicating_priority():
    data = {
        "alignment": {
            "actual_count": 18,
            "source_table_count": 17,
            "source_recount_matches_table": False,
            "source_position_recount": {
                "count": 16,
                "counting_rule": "数至太乙宫前",
                "terminal_palace": "巽",
                "path": [{"value": v} for v in (1, 8, 3, 4)],
            },
        }
    }
    witnesses = collect_verified_outputs(data)
    conflicts = collect_source_conflicts(data, witnesses)
    assert len(conflicts) == 1
    row = conflicts[0]
    assert row["finite_recorded_alternatives"] == [18, 16, 17]
    assert row["finite_alternative_enclosure_exact"] == ["16", "18"]
    assert row["source_priority"] == "not_adjudicated"
    assert row["preferred_value"] is None
    assert row["alternatives_exhaustive"] is False
    assert row["original_gate_reclassified_as_passed"] is False
    data["alignment"]["source_recount_matches_table"] = True
    with pytest.raises(RuntimeError, match="原表不符"):
        collect_source_conflicts(data, witnesses)
