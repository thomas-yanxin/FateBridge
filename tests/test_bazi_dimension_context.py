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


def test_unknown_gender_errors_on_dayun_dimension():
    person = create_person_info(1990, 5, 20, 10, "t", birth_place="北京")  # gender 未知
    result = bazi.calculate_bazi_career(person, analysis_year=2026)
    assert "error" in result
    assert "性别" in result["error"]


def test_known_gender_produces_forward_dayun_for_yang_year_male():
    person = create_person_info(1990, 5, 20, 10, "t", "男", "北京")  # 1990 庚午 阳年
    tc = bazi.calculate_bazi_career(person, analysis_year=2026)["career_analysis"][
        "timing_context"
    ]
    assert tc["dayun_pillar"] == "乙酉"  # forward (顺行) from month pillar


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
    tc = bazi.calculate_bazi_wealth(person, analysis_year=2026)["wealth_analysis"][
        "timing_context"
    ]
    assert tc["liunian_pillar"] == "丙午"  # 2026 year ganzhi
    assert tc["dayun_pillar"] == "乙酉"
    assert tc["overridden"] == {"dayun_pillar": False, "liunian_pillar": False}
    assert abs(tc["dayun_age"] - 28.56) < 0.5


def test_explicit_pillars_override_auto_derivation():
    person = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    tc = bazi.calculate_bazi_wealth(person, analysis_year=2026, dayun_pillar="壬戌")[
        "wealth_analysis"
    ]["timing_context"]
    assert tc["overridden"]["dayun_pillar"] is True
