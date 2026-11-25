"""BaZi dimension inputs, star selection and automatic timing context."""

from datetime import datetime

import pytest

import fatebridge.services.bazi as bazi
from fatebridge.services.bazi import _resolve_analysis_date
from fatebridge.utils.birth_input import create_person_info


def test_dayun_analysis_exposes_precise_start_age_and_direction() -> None:
    """With the display ``start_age`` ceil-rounded to 8 for a chart whose real
    起运 is ~7.25岁, consumers need ``start_age_precise`` to reconcile the
    fractional ``dayun_age`` and show the correct 顺/逆行 direction."""
    from fatebridge.services.timing import calculate_dayun_analysis
    from fatebridge.utils.birth_input import PersonInfo

    person = PersonInfo(
        name="zhang",
        gender="男",
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.47,
        use_true_solar_time=True,
    )
    result = calculate_dayun_analysis(person, analysis_age=30)
    info = result["dayun_info"]
    assert info["start_age"] == 8
    assert info["start_age_precise"] is not None
    # 7 < precise < 8 for this chart (roughly 7.25). Use a loose window to stay
    # resilient to precision tweaks while still catching a stale display.
    assert 7.0 <= info["start_age_precise"] < 8.0
    # dayun_age + start_age_precise must sum to the analysis age (within 1s).
    assert abs(info["dayun_age"] + info["start_age_precise"] - 30) < 0.02
    # 1990 年干 庚 (阳) + 男 → 顺行
    assert info["direction"] == "顺行"


def test_unknown_gender_limits_dayun_without_losing_natal_or_liunian():
    person = create_person_info(1990, 5, 20, 10, "t", birth_place="北京")  # gender 未知
    result = bazi.calculate_bazi_career(person, analysis_year=2026)
    assert "error" not in result
    timing = result["career_analysis"]["timing_context"]
    assert timing["dayun_pillar"] is None
    assert timing["dayun_status"] == "unavailable_gender_direction"
    assert timing["liunian_pillar"]
    assert result["career_analysis"]["evidence_chain"]["ten_gods"]


@pytest.mark.parametrize(
    "gender, expected_pillar",
    [
        ("男", "乙酉"),
        (" MaLe ", "乙酉"),
        ("乾", "乙酉"),
        ("1", "乙酉"),
        ("女", "丁丑"),
        (" FeMaLe ", "丁丑"),
        ("坤", "丁丑"),
        ("0", "丁丑"),
    ],
)
def test_known_gender_aliases_select_dayun_direction(gender, expected_pillar):
    person = create_person_info(1990, 5, 20, 10, "t", gender, "北京")  # 庚午阳年
    analysis = bazi.calculate_bazi_career(
        person, analysis_year=2026, analysis_month=10, analysis_day=12
    )["career_analysis"]
    assert analysis["timing_context"]["dayun_pillar"] == expected_pillar
    assert analysis["timing_context"]["liunian_pillar"] == "丙午"
    assert "dayun_status" not in analysis["timing_context"]


@pytest.mark.parametrize(
    "alias, canonical, expected_basis", [("乾", "男", "male"), ("坤", "女", "female")]
)
def test_gender_aliases_share_timing_and_topic_rule_selection(
    alias, canonical, expected_basis
):
    analyses = []
    for gender in (alias, canonical):
        person = create_person_info(1990, 5, 20, 10, "t", gender, "北京")
        analysis = bazi.calculate_bazi_marriage(
            person, analysis_year=2026, analysis_month=10, analysis_day=12
        )["marriage_analysis"]
        assert analysis["gender_basis"] == expected_basis
        assert (
            analysis["evidence_chain"]["topic"]["selection_basis"]
            == "gendered_traditional_correspondence"
        )
        analyses.append(analysis)
    assert analyses[0] == analyses[1]


@pytest.mark.parametrize(
    "year, month, expected_day", [(2030, 6, 30), (2025, 2, 28), (2024, 2, 29)]
)
def test_resolve_analysis_date_clamps_partial_day(
    monkeypatch, year, month, expected_day
):
    monkeypatch.setattr(
        bazi, "current_local_datetime", lambda: datetime(year, month, 15)
    )
    # The omitted year comes from the fixed civil clock; an explicit day can
    # then exceed the resolved month and is clamped only for this partial date.
    assert _resolve_analysis_date(None, month, 31) == datetime(
        year, month, expected_day
    )


@pytest.mark.parametrize("year, month", [(2030, 6), (2025, 2), (2024, 2)])
def test_resolve_analysis_date_rejects_complete_invalid_date(year, month):
    with pytest.raises(ValueError, match="day is out of range"):
        _resolve_analysis_date(year, month, 31)


def test_children_star_differs_by_gender():
    male = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    female = create_person_info(1990, 6, 15, 10, "t", "女", "北京")
    cs_m = bazi.calculate_bazi_children(male, dayun_pillar="壬戌")["children_analysis"][
        "child_star"
    ]["star"]
    cs_f = bazi.calculate_bazi_children(female, dayun_pillar="壬戌")[
        "children_analysis"
    ]["child_star"]["star"]
    assert "官杀" in cs_m  # 男命子女星 = 官杀
    assert "食伤" in cs_f  # 女命子女星 = 食伤
    assert cs_m != cs_f


def test_romance_opposite_sex_star_differs_by_gender():
    male = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    female = create_person_info(1990, 6, 15, 10, "t", "女", "北京")
    bm = bazi.calculate_bazi_romance(male, dayun_pillar="壬戌")["romance_analysis"][
        "opposite_sex_star"
    ]["basis"]
    bf = bazi.calculate_bazi_romance(female, dayun_pillar="壬戌")["romance_analysis"][
        "opposite_sex_star"
    ]["basis"]
    assert "财" in bm  # 男命异性缘 = 财
    assert "官杀" in bf  # 女命异性缘 = 官杀


def test_dimension_auto_derives_correct_dayun_and_liunian():
    person = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    tc = bazi.calculate_bazi_wealth(
        person, analysis_year=2026, analysis_month=10, analysis_day=12
    )["wealth_analysis"]["timing_context"]
    assert tc["liunian_pillar"] == "丙午"  # 2026 year ganzhi
    assert tc["dayun_pillar"] == "乙酉"
    assert tc["overridden"] == {"dayun_pillar": False, "liunian_pillar": False}
    assert tc["dayun_age"] == pytest.approx(28.88, abs=0.02)


@pytest.mark.parametrize(
    "gender, age_basis",
    [
        ("乾", "auto_derived_reference_not_override_pillar_age"),
        ("未知", "unavailable_for_override"),
    ],
)
def test_explicit_dayun_overrides_auto_derivation(gender, age_basis):
    person = create_person_info(1990, 6, 15, 10, "t", gender, "北京")
    tc = bazi.calculate_bazi_wealth(
        person,
        analysis_year=2026,
        analysis_month=10,
        analysis_day=12,
        dayun_pillar="壬戌",
    )["wealth_analysis"]["timing_context"]
    assert tc["dayun_pillar"] == "壬戌"
    assert tc["liunian_pillar"] == "丙午"
    assert tc["overridden"] == {"dayun_pillar": True, "liunian_pillar": False}
    assert tc["dayun_status"] == "explicit_override"
    assert tc["dayun_age_basis"] == age_basis
    assert tc["dayun_selection_basis"] is None
    assert tc["dayun_start_at"] is None
    assert tc["dayun_end_at"] is None
    if gender == "未知":
        assert tc["dayun_age"] is None
    else:
        assert tc["dayun_age"] == pytest.approx(28.88, abs=0.02)


def test_explicit_liunian_does_not_suppress_automatic_dayun():
    person = create_person_info(1990, 5, 20, 10, "t", "乾", "北京")
    tc = bazi.calculate_bazi_career(
        person,
        analysis_year=2026,
        analysis_month=10,
        analysis_day=12,
        liunian_pillar="甲子",
    )["career_analysis"]["timing_context"]
    assert tc["dayun_pillar"] == "乙酉"
    assert tc["liunian_pillar"] == "甲子"
    assert tc["overridden"] == {"dayun_pillar": False, "liunian_pillar": True}


@pytest.mark.parametrize("hour_branch", ["寅", "亥", "子"])
@pytest.mark.parametrize(
    "hour_stem,expected_god,has_achievement",
    [
        ("甲", "比肩", False),
        ("乙", "劫财", False),
        ("丙", "食神", True),
        ("丁", "伤官", True),
        ("戊", "偏财", True),
        ("己", "正财", True),
        ("庚", "七杀", True),
        ("辛", "正官", True),
        ("壬", "偏印", True),
        ("癸", "正印", True),
    ],
)
def test_children_hour_gods_describe_parent_symbols_not_child_abilities(
    hour_stem, expected_god, has_achievement, hour_branch
):
    """Every ten-god branch must retain facts without a child's own chart claims."""
    import json

    from fatebridge.analysis.children import ChildrenAnalysis
    from fatebridge.core.output_bazi import ChildrenAnalysis as ChildrenOutput

    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": (hour_stem, hour_branch),
    }
    result = ChildrenAnalysis.analyze_children(pillars, "女")
    ChildrenOutput.model_validate(result)
    palace = result["child_palace"]
    relationship = result["relationship"]
    assert palace["hour_pillar"] == hour_stem + hour_branch
    assert palace["hour_ten_god"] == expected_god
    assert relationship["hour_ten_god"] == expected_god
    assert set(relationship) == {"hour_ten_god", "trait", "achievement"}
    assert relationship["trait"] == palace["trait"]
    assert "命主" in relationship["trait"] and "传统象意" in relationship["trait"]
    assert isinstance(relationship["achievement"], list)
    assert bool(relationship["achievement"]) is has_achievement
    for interpretation in relationship["achievement"]:
        assert "命主" in interpretation and "传统象意" in interpretation
        assert "不推断孩子" in interpretation
    assert "不推断孩子的性格、能力或成就" in result["interpretation_scope"]
    text = json.dumps(result, ensure_ascii=False)
    for claim in (
        "子女聪慧",
        "子女聪明",
        "子女端正有出息",
        "易有官贵之子",
        "子女才华出众",
        "学业文化有成",
        "能成大事",
        "得子女财力之助",
        "亲子关系融洽",
        "亲子关系较顺",
        "聚少离多",
    ):
        assert claim not in text


def test_children_symbol_wording_preserves_star_weights_and_affinity_score():
    """A wording correction must not alter the underlying cultural classification."""
    from fatebridge.analysis.children import ChildrenAnalysis

    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": ("丙", "寅"),
    }
    result = ChildrenAnalysis.analyze_children(pillars, "女")
    assert result["child_star"]["weight"] == 3.5
    assert len(result["child_star"]["positions"]) == 5
    assert result["affinity"]["score"] == 77
    assert result["children_timing"] == {
        "timing_signals": ["本轮未取得子女星／宫的时间关系，不据此判断生育时机"]
    }
