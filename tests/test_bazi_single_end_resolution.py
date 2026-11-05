"""Source-conditioned unique子卯 correction, complete old controls retained."""

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_source_annotations import SourceCurrentCalculation
from fatebridge.services.source_comparison import calculate_bazi_source_compare

ORDER = ("year", "month", "day", "hour")


def chart(values):
    return dict(zip(ORDER, map(tuple, values)))


def test_new_v10_true_single_end_receipt_valid():
    value = calculate_bazi_source_compare("乙丑", "戊子", "丙辰", "辛卯")[
        "current_calculation"
    ]
    assert value["method_id"] == "season_root_revelation_relations_v12"
    SourceCurrentCalculation.model_validate(value)


def test_new_v10_natal_evidence_valid():
    p = chart(["乙丑", "戊子", "丙辰", "辛卯"])
    BaziEvidenceChain.model_validate(
        build_natal_evidence(p, ElementAnalysis.analyze_day_master_strength(p))
    )


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
