"""Literal seasonal tables and a rational hand calculation, independent of cycles.

Source: 三命通會·論五行旺相休囚死並寄生十二宫,
https://www.shidianguji.com/zh/book/SK1610/chapter/1kf5v6ol1tqg5
This checks the stated seasonal convention, not complete strength or prediction.
"""

from copy import deepcopy
from fractions import Fraction

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_branch_candidates import validate_punishment_resolution
from fatebridge.core.output_source_annotations import SourceCurrentCalculation
from fatebridge.core.strength import STRENGTH_METHOD_ID


@pytest.mark.parametrize(
    "months,phases",
    [
        ("寅卯", {"木": "旺", "火": "相", "土": "死", "金": "囚", "水": "休"}),
        ("巳午", {"木": "休", "火": "旺", "土": "相", "金": "死", "水": "囚"}),
        ("辰未戌丑", {"木": "囚", "火": "休", "土": "旺", "金": "相", "水": "死"}),
        ("申酉", {"木": "死", "火": "囚", "土": "休", "金": "旺", "水": "相"}),
        ("亥子", {"木": "相", "火": "死", "土": "囚", "金": "休", "水": "旺"}),
    ],
)
def test_all_twelve_month_branches_follow_literal_seasonal_table(months, phases):
    for branch in months:
        assert ElementAnalysis.seasonal_phases(branch) == phases
        pillars = dict(
            zip(
                ("year", "month", "day", "hour"),
                (("庚", "辰"), ("戊", branch), ("壬", "寅"), ("乙", "巳")),
            )
        )
        result = ElementAnalysis.analyze_day_master_strength(pillars)
        assert result["element_seasonal_phase"] == phases
        assert result["assessment"]["seasonal_phases"] == phases
        assert (
            result["element_distribution_basis"] == ElementAnalysis.DISTRIBUTION_BASIS
        )
        assert "结构计数" in result["element_distribution_basis"]
        assert "element_seasonal_phase" in result["element_distribution_basis"]


def test_corrected_phases_feed_exact_budget_without_changing_weights():
    pillars = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ("乙卯", "己卯", "辛卯", "癸卯")),
        )
    )
    result = ElementAnalysis.analyze_day_master_strength(pillars)
    assessment = result["assessment"]
    assert (
        assessment["method_id"]
        == STRENGTH_METHOD_ID
        == "season_root_revelation_relations_v12"
    )
    assert assessment["relations"] == []
    # Ten units of 卯/乙 root budget at 旺2 and revelation1.25, plus
    # rooted year乙 at 旺2 => wood27. Unrooted month己 at 死0.5 => 1/8;
    # unrooted hour癸 at 休1 => 1/4. Day辛 is not another energy vote.
    exact = assessment["threshold_arithmetic"]
    expected = {"木": "27", "火": "0", "土": "1/8", "金": "0", "水": "1/4"}
    assert exact["energies_exact"] == expected
    assert exact["support_exact"] == "1/8"
    assert exact["weaken_exact"] == "109/4"
    assert exact["share_exact"] == "1/219"
    assert Fraction(exact["support_exact"]) / (
        Fraction(exact["support_exact"]) + Fraction(exact["weaken_exact"])
    ) == Fraction(1, 219)
    assert assessment["seasonal_factors"] == {
        "旺": 2.0,
        "相": 1.5,
        "休": 1.0,
        "囚": 0.75,
        "死": 0.5,
    }
    assert assessment["parameters"]["strong_share"] == 0.60
    assert assessment["parameters"]["weak_share"] == 0.40
    BaziEvidenceChain.model_validate(build_natal_evidence(pillars, result))


@pytest.mark.parametrize(
    "method",
    [
        "season_root_revelation_relations_v10",
        "season_root_revelation_relations_v11",
        "season_root_revelation_relations_v12",
    ],
)
def test_current_punishment_contract_and_retired_method_rejection(
    method,
):
    invalid = [
        {
            "kind": "刑",
            "positions": ["month", "hour"],
            "status": "resolved_by_combination",
        }
    ]
    payload = {"method_id": method, "assessment": {"relations": deepcopy(invalid)}}
    if method != STRENGTH_METHOD_ID:
        # Retired calculation labels are rejected by the public receipt model;
        # they no longer select a historical implementation or validation policy.
        with pytest.raises(ValidationError, match="只接收当前旺衰计算回执"):
            SourceCurrentCalculation.model_validate(payload)
        return
    with pytest.raises(ValueError, match="实际会合覆盖"):
        validate_punishment_resolution(method, invalid)
    with pytest.raises(ValidationError, match="实际会合覆盖"):
        SourceCurrentCalculation.model_validate(payload)
