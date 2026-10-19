import pytest

from fatebridge.analysis.compatibility import AdvancedCompatibility
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.rules import BaZiRules
from fatebridge.services.calculation import calculate_destiny_analysis
from fatebridge.utils.birth_input import create_person_info


def _build_minimal_analysis(
    *,
    day_stem: str,
    day_branch: str,
    useful_elements: list[str],
    avoid_elements: list[str],
    useful_ten_gods: list[str],
    recognized_structures: list[dict] | None = None,
    element_distribution: dict[str, float] | None = None,
):
    return {
        "four_pillars": {
            "year": {"stem": "甲", "branch": "申"},
            "month": {"stem": "丙", "branch": "子"},
            "day": {"stem": day_stem, "branch": day_branch},
            "hour": {"stem": "庚", "branch": "辰"},
        },
        "day_master": {
            "stem": day_stem,
            "element": ElementAnalysis.analyze_day_master_strength(
                {
                    "year": ("甲", "申"),
                    "month": ("丙", "子"),
                    "day": (day_stem, day_branch),
                    "hour": ("庚", "辰"),
                }
            )["day_element"],
            "strength": "中和",
        },
        "element_distribution": element_distribution
        or {"木": 20.0, "火": 20.0, "土": 20.0, "金": 20.0, "水": 20.0},
        "favorable_elements": useful_elements,
        "patterns": {
            "harmony": {"three_harmony": [], "half_harmony": [], "six_harmony": []},
            "special": {
                "recognized_structures": recognized_structures or [],
                "metadata": {
                    "counts": {"horses": 2},
                    "branch_attributes": {},
                },
            },
        },
        "structure_profile": {
            "dominant_structure": (
                (
                    recognized_structures
                    or [{"key": "default_support", "label": "扶抑调候"}]
                )[0]
            ),
            "secondary_structures": (recognized_structures or [])[1:],
            "recognized_structures": recognized_structures or [],
            "useful_elements": useful_elements,
            "avoid_elements": avoid_elements,
            "useful_ten_gods": useful_ten_gods,
            "decision_basis": [],
            "harmony_effects": [],
        },
    }


def test_build_structure_profile_detects_yang_ren_jia_sha():
    pillars = {
        "year": ("庚", "申"),
        "month": ("己", "卯"),
        "day": ("甲", "寅"),
        "hour": ("庚", "午"),
    }

    element_analysis = ElementAnalysis.comprehensive_analysis(pillars)
    structure_profile = BaZiRules.build_structure_profile(
        pillars=pillars,
        element_analysis=element_analysis,
        harmony_patterns=BaZiRules.check_harmony_patterns(pillars),
        clash_patterns=BaZiRules.check_clash_patterns(pillars),
        special_patterns=BaZiRules.analyze_special_patterns(pillars),
    )

    assert structure_profile["dominant_structure"]["label"] == "羊刃驾杀"
    assert "七杀" in structure_profile["useful_ten_gods"]
    assert any(
        item["label"] == "羊刃驾杀"
        for item in structure_profile["recognized_structures"]
    )


def test_analyze_harmony_effects_returns_structured_event_payload():
    pillars = {
        "year": ("甲", "寅"),
        "month": ("丙", "午"),
        "day": ("戊", "戌"),
        "hour": ("辛", "卯"),
    }
    element_analysis = ElementAnalysis.comprehensive_analysis(pillars)
    structure_profile = BaZiRules.build_structure_profile(
        pillars=pillars,
        element_analysis=element_analysis,
        harmony_patterns=BaZiRules.check_harmony_patterns(pillars),
        clash_patterns=BaZiRules.check_clash_patterns(pillars),
        special_patterns=BaZiRules.analyze_special_patterns(pillars),
    )

    events = BaZiRules.analyze_harmony_effects(pillars, structure_profile)

    triple_event = next(event for event in events if event["type"] == "three_harmony")
    assert triple_event["result_element"] == "火"
    assert "result_element" in triple_event
    assert "strengthens" in triple_event
    assert "consumes" in triple_event
    assert "impact_on_day_master" in triple_event
    assert "impact_on_structure" in triple_event


def test_analyze_combined_chart_events_detects_cross_person_three_harmony():
    pillars1 = {
        "year": ("甲", "申"),
        "month": ("丁", "子"),
        "day": ("甲", "寅"),
        "hour": ("丙", "午"),
    }
    pillars2 = {
        "year": ("乙", "辰"),
        "month": ("己", "酉"),
        "day": ("辛", "卯"),
        "hour": ("壬", "戌"),
    }

    merged = BaZiRules.analyze_combined_chart_events(pillars1, pillars2)

    event = next(
        item
        for item in merged["events"]
        if item["type"] == "three_harmony" and item["result_element"] == "水"
    )
    assert event["source_map"]["申"][0]["person"] == "person1"
    assert event["source_map"]["辰"][0]["person"] == "person2"


def test_pattern_synergy_ignores_special_metadata_keys():
    recognized = [{"key": "yang_ren_jia_sha", "label": "羊刃驾杀"}]
    analysis1 = _build_minimal_analysis(
        day_stem="甲",
        day_branch="子",
        useful_elements=["金", "土"],
        avoid_elements=["火"],
        useful_ten_gods=["七杀"],
        recognized_structures=recognized,
    )
    analysis2 = _build_minimal_analysis(
        day_stem="己",
        day_branch="丑",
        useful_elements=["木", "水"],
        avoid_elements=["金"],
        useful_ten_gods=["正官"],
        recognized_structures=[],
    )

    result = AdvancedCompatibility._analyze_pattern_synergy(analysis1, analysis2)

    assert not any("counts" in detail for detail in result["details"])
    assert not any("branch_attributes" in detail for detail in result["details"])
    assert "supportive_patterns" in result
    assert "tension_patterns" in result
    assert "risk_patterns" in result


def test_favorable_synergy_reads_top_level_distribution_and_structure_profile():
    analysis1 = _build_minimal_analysis(
        day_stem="甲",
        day_branch="子",
        useful_elements=["金", "土"],
        avoid_elements=["火"],
        useful_ten_gods=["七杀"],
        element_distribution={
            "木": 12.0,
            "火": 8.0,
            "土": 28.0,
            "金": 30.0,
            "水": 22.0,
        },
    )
    analysis2 = _build_minimal_analysis(
        day_stem="己",
        day_branch="丑",
        useful_elements=["木", "水"],
        avoid_elements=["金"],
        useful_ten_gods=["正官"],
        element_distribution={
            "木": 24.0,
            "火": 10.0,
            "土": 18.0,
            "金": 16.0,
            "水": 32.0,
        },
    )

    result = AdvancedCompatibility._analyze_favorable_synergy(analysis1, analysis2)

    assert result["score"] > 60
    assert result["supportive_patterns"]
    assert "score_basis" in result
    assert "risk_reasons" in result


@pytest.mark.parametrize("direction", ["forward", "reverse", "both", "neither"])
def test_favorable_synergy_bidirectional_label_uses_actual_support_directions(
    direction,
):
    # All four cases score 74 under the existing rules. Shared preferences and
    # useful ten gods can reach this band without any directional support.
    first = {
        "element_distribution": {"水": 100.0},
        "structure_profile": {"useful_elements": [], "useful_ten_gods": []},
    }
    second = {
        "element_distribution": {"水": 100.0},
        "structure_profile": {"useful_elements": [], "useful_ten_gods": []},
    }
    if direction in {"forward", "reverse"}:
        first["structure_profile"]["useful_elements"] = ["木", "火"]
        second["element_distribution"] = {"木": 16.0, "火": 16.0, "水": 68.0}
        if direction == "reverse":
            first, second = second, first
        expected_directions = {
            ("第二人", "第一人") if direction == "forward" else ("第一人", "第二人")
        }
        expected_basis_deltas = [7, 7]
    elif direction == "both":
        first["structure_profile"]["useful_elements"] = ["木"]
        second["structure_profile"]["useful_elements"] = ["火"]
        first["element_distribution"] = {"火": 16.0, "水": 84.0}
        second["element_distribution"] = {"木": 16.0, "水": 84.0}
        expected_directions = {("第一人", "第二人"), ("第二人", "第一人")}
        expected_basis_deltas = [7, 7]
    else:
        for person in (first, second):
            person["structure_profile"]["useful_elements"] = ["木", "火"]
            person["structure_profile"]["useful_ten_gods"] = ["正印", "偏印"]
        expected_directions = set()
        expected_basis_deltas = [8]

    result = AdvancedCompatibility._analyze_favorable_synergy(first, second)
    assert result["score"] == 74.0
    assert result["synergy_level"] == (
        "双向互助" if direction == "both" else "协同较好"
    )
    assert {
        (item["source"], item["target"]) for item in result["supportive_patterns"]
    } == expected_directions
    assert len(result["supportive_patterns"]) == (0 if direction == "neither" else 2)
    assert [
        int(item.rsplit("(+", 1)[1].rstrip(")")) for item in result["score_basis"]
    ] == expected_basis_deltas
    assert result["tension_patterns"] == []
    if direction == "neither":
        assert result["useful_ten_gods_support"][0]["common_ten_gods"] == [
            "偏印",
            "正印",
        ]
    else:
        assert result["mutual_help"] == [
            item["description"] for item in result["supportive_patterns"]
        ]


def test_favorable_synergy_label_preserves_scores_events_and_three_surface_parity():
    from fastapi.testclient import TestClient

    import fatebridge.api as api
    from tests.fixtures.surface_payloads import REST_POST_CASES
    from tests.test_agentic_replay import business, cli, native

    inputs = REST_POST_CASES["/api/compatibility"]()
    controls = {"as_of": "2026-10-20T10:00:00+08:00"}
    # These are public test fixtures; use the existing auth-free transport
    # fixture convention so local API-key configuration cannot change the test.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            api,
            "API_KEY_AUTHENTICATOR",
            api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
        )
        response = TestClient(api.app).post(
            "/api/compatibility", json=inputs, params=controls
        )
    protocol = native("two_person_compatibility", inputs, controls)
    code, output = cli("two_person_compatibility", inputs, controls)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    expected = business(response.json())
    assert expected == business(protocol.structured_content) == business(output)
    assert expected["summary"]["overall_score"] == 69.6
    assert expected["summary"]["scoring"]["unrounded_score"] == 69.61
    dimensions = expected["summary"]["scoring"]["dimensions"]
    assert {key: item["score"] for key, item in dimensions.items()} == {
        "element_balance": 73.0,
        "favorable_synergy": 77.0,
        "ten_gods_relationship": 94.0,
        "pattern_synergy": 36.0,
        "traditional_analysis": 39.0,
    }
    assert {key: item["weight"] for key, item in dimensions.items()} == {
        "element_balance": 0.25,
        "favorable_synergy": 0.35,
        "ten_gods_relationship": 0.17,
        "pattern_synergy": 0.18,
        "traditional_analysis": 0.05,
    }
    synergy = expected["detailed_analysis"]["favorable_synergy"]
    assert synergy["synergy_level"] == "协同较好"
    assert synergy["score_basis"] == [
        "第一人土较旺，对第二人有稳定补益(+7)",
        "第一人金占比高，能明显补到第二人的可用之气(+10)",
    ]
    assert [item["element"] for item in synergy["supportive_patterns"]] == ["土", "金"]
    assert {
        (item["source"], item["target"]) for item in synergy["supportive_patterns"]
    } == {("第一人", "第二人")}


def test_tian_ke_di_chong_is_reported_as_tension_pattern():
    analysis1 = _build_minimal_analysis(
        day_stem="甲",
        day_branch="子",
        useful_elements=["土", "金"],
        avoid_elements=["火"],
        useful_ten_gods=["七杀", "正官"],
    )
    analysis2 = _build_minimal_analysis(
        day_stem="己",
        day_branch="午",
        useful_elements=["木", "水"],
        avoid_elements=["金"],
        useful_ten_gods=["正官", "七杀"],
    )

    result = AdvancedCompatibility._analyze_pattern_synergy(analysis1, analysis2)

    assert any(item["label"] == "天克地冲" for item in result["tension_patterns"])
    assert not any(item["label"] == "天克地冲" for item in result["risk_patterns"])


def test_element_balance_treats_needed_control_as_favorable():
    # person1 日主甲(木) 克 person2 日主戊(土)。对 person2 而言，木是其官杀。
    # person2 的格局把木列为喜用（如羊刃驾杀需官杀），此时"被克"是格局所需，
    # 不应按无情之克扣分。
    analysis1 = _build_minimal_analysis(
        day_stem="甲",
        day_branch="子",
        useful_elements=["水", "木"],
        avoid_elements=["土", "火", "金"],
        useful_ten_gods=["正印"],
    )
    analysis2 = _build_minimal_analysis(
        day_stem="戊",
        day_branch="辰",
        useful_elements=["木", "水"],
        avoid_elements=["土", "火", "金"],
        useful_ten_gods=["正官", "七杀"],
    )

    result = AdvancedCompatibility._analyze_element_balance(analysis1, analysis2)

    assert result["balance_type"] == "相克有情"
    assert not any("压制感" in detail for detail in result["details"])
    # 与无情之克(-8)相比，有情之克不扣分，总分应高于扣分基准。
    assert result["score"] >= 65.0


def test_element_balance_still_penalizes_wujing_control():
    # person1 日主甲(木) 克 person2 日主戊(土)，但木落在 person2 的忌神区间，
    # 且 person2 的土也非 person1 喜用——双方都不得益，仍按无情之克扣分。
    analysis1 = _build_minimal_analysis(
        day_stem="甲",
        day_branch="子",
        useful_elements=["水", "木"],
        avoid_elements=["土", "火", "金"],
        useful_ten_gods=["正印"],
    )
    analysis2 = _build_minimal_analysis(
        day_stem="戊",
        day_branch="辰",
        useful_elements=["火", "土"],
        avoid_elements=["木", "水", "金"],
        useful_ten_gods=["正印"],
    )

    result = AdvancedCompatibility._analyze_element_balance(analysis1, analysis2)

    assert result["balance_type"] == "相克制约"
    assert any("压制感" in detail for detail in result["details"])


def test_calculate_destiny_analysis_exposes_structure_profile():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_destiny_analysis(person)

    assert "structure_profile" in result
    assert (
        result["favorable_elements"] == result["structure_profile"]["useful_elements"]
    )
    assert "recognized_structures" in result["patterns"]["special"]
    assert "metadata" in result["patterns"]["special"]


def test_comprehensive_summary_reads_normalized_score_key():
    """traditional_analysis 维度用 normalized_score 键，摘要必须回退读取它。

    回归历史 bug：_generate_comprehensive_summary 曾用 .get("score", 0)，对
    traditional_analysis（只有 normalized_score）静默拿到 0，把它恒判为「挑战」。
    现在该维度近中性（48 分，落在 46<score<68 区间）应既非优势也非挑战。
    """
    result = {
        "overall_score": 60.0,
        "strengths": [],
        "challenges": [],
        "detailed_analysis": {
            # 近中性的传统维度：仅一处轻微六冲，归一化后 48 分。
            "traditional_analysis": {
                "normalized_score": 48.0,
                "traditional_deviation": -0.2,
                "details": ["子与午六冲"],
            },
            # 明确为挑战的常规维度，验证正常路径仍生效。
            "ten_gods_relationship": {
                "score": 40.0,
                "details": ["十神层面存在明显克泄"],
            },
        },
    }

    summarized = AdvancedCompatibility._generate_comprehensive_summary(result)

    # 48 分既不进 strengths（≥68）也不进 challenges（≤46）。
    assert "子与午六冲" not in summarized["challenges"]
    assert "子与午六冲" not in summarized["strengths"]
    # 常规维度按真实 score 正确归入挑战，证明判定确实读到了分数而非恒 0。
    assert "十神层面存在明显克泄" in summarized["challenges"]


def test_compatibility_score_rewards_three_harmony_and_penalises_harm() -> None:
    """``BaZiRules.calculate_compatibility_score`` previously only scored 六合
    and 六冲. Three-harmony, half-harmony, 六害 and 三刑 are now included so
    the traditional_compatibility block reflects classical jipan matching."""
    from fatebridge.core.rules import BaZiRules

    # 一方: 申子辰 水三合 分散在三柱; 二方: 亥子丑 混合 (主要对冲六合已有)
    pillars_full_triple = {
        "year": ("甲", "申"),
        "month": ("乙", "子"),
        "day": ("丙", "辰"),  # 三合水局齐
        "hour": ("丁", "卯"),
    }
    # 对方也有自己部分同组支, 跨盘凑成 三合
    pillars_partial = {
        "year": ("戊", "申"),  # 跨盘与前者 辰 凑 半合
        "month": ("己", "子"),
        "day": ("庚", "午"),  # 日支 六冲 前者的子
        "hour": ("辛", "未"),  # 前者日支辰 与 未 六害
    }
    result = BaZiRules.calculate_compatibility_score(
        pillars_full_triple, pillars_partial
    )
    joined = " | ".join(result["details"])
    assert "半合" in joined, joined
    # Six harm shows as "相害" note — we use 六害 consistently
    assert "六害" in joined, joined
    assert result["harmony_score"] > 0
    assert result["clash_score"] > 0


def test_compatibility_score_detects_cross_chart_triple_punishment() -> None:
    from fatebridge.core.rules import BaZiRules

    pillars_a = {
        "year": ("甲", "寅"),
        "month": ("乙", "卯"),
        "day": ("丙", "辰"),
        "hour": ("丁", "巳"),
    }
    pillars_b = {
        "year": ("戊", "申"),
        "month": ("己", "酉"),
        "day": ("庚", "戌"),
        "hour": ("辛", "亥"),
    }
    result = BaZiRules.calculate_compatibility_score(pillars_a, pillars_b)
    # 寅巳申 三刑 已由 前者 (寅/巳) + 后者 (申) 合成
    assert any("三刑" in d for d in result["details"]), result["details"]
    assert result["clash_score"] >= 5
