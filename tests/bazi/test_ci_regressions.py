"""Related contract regressions with shared imports; original cases retained."""

import re
from copy import deepcopy
from fractions import Fraction

import pytest
from pydantic import ValidationError

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.analysis.marriage import MarriageAnalysis
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.output_branch_candidates import validate_punishment_resolution
from fatebridge.core.output_source_annotations import SourceCurrentCalculation
from fatebridge.core.strength import STRENGTH_METHOD_ID
from fatebridge.utils.data import Element, count_element_distribution


@pytest.mark.parametrize("is_male", [True, False])
@pytest.mark.parametrize(
    "order", [("year", "month", "day", "hour"), ("hour", "day", "month", "year")]
)
def test_spouse_stars_at_both_ends_do_not_select_timing_by_iteration_order(
    is_male, order
):
    # Both visible spouse-star conventions hit the year and hour positions.
    # The existing rules attach opposite ordinal cues to those positions;
    # there is no declared priority that lets one silently replace the other.
    p = {
        "year": ("戊" if is_male else "庚", "辰"),
        "month": ("丙", "午"),
        "day": ("甲", "子"),
        "hour": ("己" if is_male else "辛", "巳"),
    }
    result = MarriageAnalysis._predict_marriage_timing(
        {key: p[key] for key in order}, "甲", "子", is_male
    )
    assert result["marriage_tendency"] == "早晚信号并存，未裁定"
    assert any("早婚倾向" in note for note in result["tendency_notes"])
    assert any("晚婚倾向" in note for note in result["tendency_notes"])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("count", [1, 2, 3])
def test_favorable_conflict_explanation_reconciles_with_actual_deduction(
    reverse, count
):
    selected = ["木", "火", "土"][:count]
    first = {"structure_profile": {"useful_elements": selected}}
    second = {"structure_profile": {"avoid_elements": selected}}
    if reverse:
        first, second = second, first
    result = AdvancedCompatibility._analyze_favorable_synergy(first, second)
    deltas = [
        int(re.search(r"\((-?\d+)\)$", row).group(1)) for row in result["score_basis"]
    ]
    assert result["score"] == 60 + sum(deltas) == 60 - 8 * count


@pytest.mark.parametrize("count", [1, 2, 3, 4])
@pytest.mark.parametrize(
    "dimension,base,cap",
    [("favorable_synergy", 60, 8), ("ten_gods_relationship", 65, 10)],
)
def test_shared_ten_god_bonus_is_included_in_the_public_score_explanation(
    count, dimension, base, cap
):
    selected = ["正印", "偏印", "食神", "伤官"][:count]
    person = {
        "day_master": {"stem": "甲"},
        "structure_profile": {"useful_ten_gods": selected},
    }
    result = (
        AdvancedCompatibility._analyze_favorable_synergy(person, person)
        if dimension == "favorable_synergy"
        else AdvancedCompatibility._analyze_ten_gods_relationship(
            person, person, RelationshipType.GENERAL
        )
    )
    deltas = [
        int(re.search(r"\(([+-]?\d+)\)$", row).group(1))
        for row in result["score_basis"]
    ]
    assert result["score"] == base + sum(deltas) == base + min(cap, count * 3)


def test_conflicting_marriage_cues_match_rest_mcp_and_cli(monkeypatch):
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from tests.evaluation.test_agentic_replay import business, cli, native

    # Fabricated regression input: 戊辰 / 戊午 / 甲午 / 戊辰.
    # Birth facts and timing overrides are explicit in all three calls.
    inputs = {
        "name": "虚构婚期相反信号回归",
        "birth_year": 1988,
        "birth_month": 6,
        "birth_day": 8,
        "birth_hour": 8,
        "birth_minute": 0,
        "birth_second": 0,
        "gender": "男",
        "birth_timezone": "+08:00",
        "use_true_solar_time": False,
        "dayun_pillar": "甲子",
        "liunian_pillar": "丙午",
    }
    controls = {"as_of": "2026-11-03T10:00:00+08:00", "response_char_limit": 0}
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        "/api/cn/bazi/marriage", json=inputs, params=controls
    )
    protocol = native("bazi_marriage", inputs, controls)
    code, local = cli("bazi_marriage", inputs, controls)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    expected = business(response.json())
    assert expected == business(protocol.structured_content) == business(local)
    assert expected["marriage_analysis"]["marriage_timing"]["marriage_tendency"] == (
        "早晚信号并存，未裁定"
    )


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


@pytest.mark.parametrize(
    "branch,expected",
    [
        ("子", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("丑", {"木": 1, "火": 0, "土": 0.8, "金": 0.3, "水": 0.3}),
        ("寅", {"木": 1.8, "火": 0.3, "土": 0.3, "金": 0, "水": 0}),
        ("卯", {"木": 1.8, "火": 0, "土": 0, "金": 0, "水": 0}),
        ("辰", {"木": 1.3, "火": 0, "土": 0.8, "金": 0, "水": 0.3}),
        ("巳", {"木": 1, "火": 0.8, "土": 0.3, "金": 0.3, "水": 0}),
        ("午", {"木": 1, "火": 0.8, "土": 0.3, "金": 0, "水": 0}),
        ("未", {"木": 1.3, "火": 0.3, "土": 0.8, "金": 0, "水": 0}),
        ("申", {"木": 1, "火": 0, "土": 0.3, "金": 0.8, "水": 0.3}),
        ("酉", {"木": 1, "火": 0, "土": 0, "金": 0.8, "水": 0}),
        ("戌", {"木": 1, "火": 0.3, "土": 0.8, "金": 0.3, "水": 0}),
        ("亥", {"木": 1.3, "火": 0, "土": 0, "金": 0, "水": 0.8}),
    ],
)
def test_all_twelve_branches_match_hand_counted_weights(branch, expected):
    actual = count_element_distribution({"day": ("甲", branch)})
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        expected, rel=0, abs=1e-12
    )


def test_four_pillars_match_hand_counted_weights():
    pillars = {
        "year": ("庚", "午"),
        "month": ("辛", "巳"),
        "day": ("辛", "巳"),
        "hour": ("甲", "午"),
    }
    actual = count_element_distribution(pillars)
    # Three metal stems, one wood stem; 午 has 丁/己 and 巳 has 丙/庚/戊.
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        {"木": 1, "火": 3.2, "土": 1.2, "金": 3.6, "水": 0}, rel=0, abs=1e-12
    )


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("甲", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("乙", {"木": 1, "火": 0, "土": 0, "金": 0, "水": 0.8}),
        ("丙", {"木": 0, "火": 1, "土": 0, "金": 0, "水": 0.8}),
        ("丁", {"木": 0, "火": 1, "土": 0, "金": 0, "水": 0.8}),
        ("戊", {"木": 0, "火": 0, "土": 1, "金": 0, "水": 0.8}),
        ("己", {"木": 0, "火": 0, "土": 1, "金": 0, "水": 0.8}),
        ("庚", {"木": 0, "火": 0, "土": 0, "金": 1, "水": 0.8}),
        ("辛", {"木": 0, "火": 0, "土": 0, "金": 1, "水": 0.8}),
        ("壬", {"木": 0, "火": 0, "土": 0, "金": 0, "水": 1.8}),
        ("癸", {"木": 0, "火": 0, "土": 0, "金": 0, "水": 1.8}),
    ],
)
def test_all_ten_stems_match_hand_counted_weights(stem, expected):
    actual = count_element_distribution({"day": (stem, "子")})
    assert {element.value: value for element, value in actual.items()} == pytest.approx(
        expected, rel=0, abs=1e-12
    )


def test_empty_input_includes_every_element_zero_initialised():
    assert count_element_distribution({}) == {element: 0.0 for element in Element}
