"""Compare opposite-degree readings against their exact printed witnesses."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao.guolao_classical import MANSIONS
from fatebridge.core.guolao.guolao_palace_profiles import (
    NLC166_MANSIONS,
    NLC166_PALACES,
    PROFILES,
    WIKISOURCE_PALACES,
    HistoricalPalaceProfile,
    PalaceEntrance,
    mansion_angle,
)

__all__ = [
    "HistoricalPalaceProfile",
    "NLC166_MANSIONS",
    "NLC166_PALACES",
    "OPPOSITE_EXAMPLES",
    "PROFILES",
    "PalaceEntrance",
    "WIKISOURCE_PALACES",
    "audit_opposite_examples",
]
from fatebridge.core.guolao.guolao_grid import load_grid

OPPOSITE_EXAMPLES = (
    Path(__file__).resolve().parents[2] / "data/guolao/opposite-degree-examples-v1.json"
)


def audit_opposite_examples(profile: HistoricalPalaceProfile) -> dict[str, Any]:
    """Expose why a perfect integer-bin fit does not establish a source method."""

    raw = OPPOSITE_EXAMPLES.read_bytes()
    source_examples = json.loads(raw)
    grid = load_grid()
    grid_binding = source_examples["grid_binding"]
    if (
        grid_binding["source_id"] != grid.source_id
        or grid_binding["source_image_sha256"] != grid.source_image_sha256
        or grid_binding["data_sha256"] != grid.data_sha256
        or grid_binding["marker_data_sha256"] != grid.marker_data_sha256
    ):
        raise ValueError("对照矩阵或扫描已变化，须重新核读例子，不跨版本套用")
    cases = source_examples["cases"]
    case_ids = [case["id"] for case in cases]
    source_ids = [source["id"] for source in source_examples["sources"]]
    if (
        not cases
        or len(case_ids) != len(set(case_ids))
        or set(case_ids) != set(source_examples["expected_case_ids"])
        or len(source_ids) != len(set(source_ids))
        or {case["source_document_id"] for case in cases} != set(source_ids)
    ):
        raise ValueError("具名原例及来源须完整且唯一，不能删例或重复计数")
    for case in cases:
        cell = grid.cell(case["source_branch"], case["declared_column"])
        if cell["numeral_value"] != case["source_degree"]:
            raise ValueError("显式来源格与原例整数不符，不能挪列修复")
    # Exhaust all shared shifts that remain inside all three printed rows.
    shifts = []
    lower = max(1 - case["declared_column"] for case in cases)
    upper = min(30 - case["declared_column"] for case in cases)
    for shift in range(lower, upper + 1):
        comparisons = []
        for case in cases:
            cell = grid.cell(case["target_branch"], case["declared_column"] + shift)
            value = cell["numeral_value"]
            comparisons.append(
                {
                    "case_id": case["id"],
                    "target_cell": cell,
                    "numeric_match": (
                        None if value is None else value == case["target_degree"]
                    ),
                    "mansion_context_accepted": False,
                }
            )
        shifts.append(
            {
                "shift": shift,
                "cases": comparisons,
                "has_known_numeric_counterexample": any(
                    c["numeric_match"] is False for c in comparisons
                ),
                "all_numeric_matches": all(
                    c["numeric_match"] is True for c in comparisons
                ),
            }
        )

    candidates = []
    for basis in ["from_entrance", "to_exit"]:
        results = []
        for case in cases:
            candidate = profile.transfer_candidate(
                mansion=case["source_mansion"],
                degree_du=Fraction(case["source_degree"]),
                source_branch=case["source_branch"],
                target_branch=case["target_branch"],
                basis=basis,
            )
            point = candidate["target_point"]
            exact_match = False
            bin_match = False
            sensitivity = None
            if point is not None:
                degree = Fraction(point["degree_in_mansion_du_exact"])
                expected = Fraction(case["target_degree"])
                exact_match = (
                    point["mansion"] == case["target_mansion"] and degree == expected
                )
                bin_match = (
                    point["mansion"] == case["target_mansion"]
                    and degree.numerator // degree.denominator == expected
                )
                # A declared sensitivity hypothesis, not transcribed precision:
                # input n <= x < n+1. Affine candidates preserve its unit width.
                offset = Fraction(candidate["target_offset_du_exact"])
                source_offset = Fraction(
                    candidate["source_point"]["degree_in_branch_interval_du_exact"]
                )
                source_mansion_width = profile.table.widths_du[
                    MANSIONS.index(case["source_mansion"])
                ]
                if (
                    Fraction(case["source_degree"] + 1) <= source_mansion_width
                    and source_offset + 1 <= profile.width(case["source_branch"])
                    and offset + 1 <= profile.width(case["target_branch"])
                ):
                    start = Fraction(point["angle_from_jiao_du_exact"])
                    target_start = mansion_angle(
                        profile.table, case["target_mansion"], expected
                    )
                    circle = profile.table.circle_du
                    overlap = max(
                        max(
                            Fraction(),
                            min(start + 1, target_start + n * circle + 1)
                            - max(start, target_start + n * circle),
                        )
                        for n in [-1, 0, 1]
                    )
                    sensitivity = {
                        "input_interval_du_exact": [
                            str(case["source_degree"]),
                            str(case["source_degree"] + 1),
                        ],
                        "endpoint_convention": "lower_inclusive_upper_exclusive",
                        "input_interval_is_source_fact": False,
                        "target_interval_start_from_jiao_du_exact": str(start),
                        "target_interval_width_du_exact": "1",
                        "overlap_with_expected_unit_bin_du_exact": str(overlap),
                        "whole_input_interval_matches_expected_unit_bin": overlap == 1,
                    }
            results.append(
                {
                    "case": case,
                    "candidate": candidate,
                    "exact_literal_point_match": exact_match,
                    "floor_bin_match_if_extra_hypothesis": bin_match,
                    "unit_interval_sensitivity_hypothesis": sensitivity,
                }
            )
        candidates.append(
            {
                "basis": basis,
                "cases": results,
                "all_exact_literal_points_match": all(
                    r["exact_literal_point_match"] for r in results
                ),
                "all_nominal_points_floor_into_expected_bins": all(
                    r["floor_bin_match_if_extra_hypothesis"] for r in results
                ),
                "floor_is_source_fact": False,
                "candidate_accepted": False,
            }
        )
    return {
        "audit_id": source_examples["id"],
        "data_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "cross_source_candidate_comparison_not_method_acceptance",
        "case_ids": case_ids,
        "profile": profile.audit(),
        "grid_binding": source_examples["grid_binding"],
        "source_documents": source_examples["sources"],
        "constant_column_shift_candidates": shifts,
        "any_shared_constant_shift_matches_all_numeric_cases": any(
            s["all_numeric_matches"] for s in shifts
        ),
        "every_shared_shift_has_known_numeric_counterexample": all(
            s["has_known_numeric_counterexample"] for s in shifts
        ),
        "coordinate_candidates": candidates,
        "book_methods_assumed_identical": False,
        "quantization_policy_accepted": False,
        "best_candidate_selected": False,
        "life_degree_accepted": False,
        "used_in_native_birth_chart": False,
        "real_world_prediction_cases": 0,
    }
