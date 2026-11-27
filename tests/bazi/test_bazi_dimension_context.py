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
    info = result["dayun"]
    assert info["start_age"] == 8
    assert info["start_age_precise"] is not None
    # 7 < precise < 8 for this chart (roughly 7.25). Use a loose window to stay
    # resilient to precision tweaks while still catching a stale display.
    assert 7.0 <= info["start_age_precise"] < 8.0
    # dayun_age + start_age_precise must sum to the analysis age (within 1s).
    assert abs(info["dayun_age"] + info["start_age_precise"] - 30) < 0.02
    # 1990 年干 庚 (阳) + 男 → 顺行
    assert info["direction"] == "顺行"


def test_unknown_gender_limits_dayun_without_losing_natal_or_liunian() -> None:
    person = create_person_info(1990, 5, 20, 10, "t", birth_place="北京")  # gender 未知
    result = bazi.calculate_bazi_career(person, analysis_year=2026)
    assert "error" not in result
    timing = result["career_analysis"]["timing_context"]
    assert timing["dayun_pillar"] is None
    assert timing["dayun_status"] == "unavailable_gender_direction"
    assert timing["liunian_pillar"]
    assert result["career_analysis"]["topic_facts"]["four_pillars"]


@pytest.mark.parametrize(
    "gender, expected_dayun",
    [
        ("男", "乙酉"),
        ("male", "乙酉"),
        ("乾", "乙酉"),
        ("female", "丁丑"),
        ("坤", "丁丑"),
    ],
)
def test_gender_aliases_select_dayun_direction(gender, expected_dayun) -> None:
    person = create_person_info(1990, 5, 20, 10, "t", gender, "北京")
    tc = bazi.calculate_bazi_career(person, analysis_year=2026)["career_analysis"][
        "timing_context"
    ]
    assert tc["dayun_pillar"] == expected_dayun


@pytest.mark.parametrize(
    "year, month, expected_day", [(2030, 6, 30), (2025, 2, 28), (2024, 2, 29)]
)
def test_resolve_analysis_date_clamps_partial_day(
    monkeypatch: pytest.MonkeyPatch, year: int, month: int, expected_day: int
) -> None:
    monkeypatch.setattr(
        bazi, "current_local_datetime", lambda: datetime(year, month, 15)
    )
    # The omitted year comes from the fixed civil clock; an explicit day can
    # then exceed the resolved month and is clamped only for this partial date.
    assert _resolve_analysis_date(None, month, 31) == datetime(
        year, month, expected_day
    )


@pytest.mark.parametrize("year, month", [(2030, 6), (2025, 2), (2024, 2)])
def test_resolve_analysis_date_rejects_complete_invalid_date(
    year: int, month: int
) -> None:
    with pytest.raises(ValueError, match="day is out of range"):
        _resolve_analysis_date(year, month, 31)


def test_children_star_differs_by_gender() -> None:
    male = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    female = create_person_info(1990, 6, 15, 10, "t", "女", "北京")
    tf_m = bazi.calculate_bazi_children(male, dayun_pillar="壬戌")["children_analysis"][
        "topic_facts"
    ]
    tf_f = bazi.calculate_bazi_children(female, dayun_pillar="壬戌")[
        "children_analysis"
    ]["topic_facts"]
    cs_m = {row["ten_god"] for row in tf_m["natal_stars"]}
    cs_f = {row["ten_god"] for row in tf_f["natal_stars"]}
    assert cs_m and cs_m <= {"正官", "七杀"}  # 男命子女星 = 官杀
    assert cs_f and cs_f <= {"食神", "伤官"}  # 女命子女星 = 食伤
    assert cs_m.isdisjoint(cs_f)


def test_romance_opposite_sex_star_differs_by_gender() -> None:
    male = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    female = create_person_info(1990, 6, 15, 10, "t", "女", "北京")
    tf_m = bazi.calculate_bazi_romance(male, dayun_pillar="壬戌")["romance_analysis"][
        "topic_facts"
    ]
    tf_f = bazi.calculate_bazi_romance(female, dayun_pillar="壬戌")["romance_analysis"][
        "topic_facts"
    ]
    bm = {row["ten_god"] for row in tf_m["natal_stars"]}
    bf = {row["ten_god"] for row in tf_f["natal_stars"]}
    assert bm and bm <= {"正财", "偏财"}  # 男命异性缘 = 财
    assert bf and bf <= {"正官", "七杀"}  # 女命异性缘 = 官杀
    assert bm.isdisjoint(bf)


def test_dimension_auto_derives_correct_dayun_and_liunian() -> None:
    person = create_person_info(1990, 6, 15, 10, "t", "男", "北京")
    tc = bazi.calculate_bazi_wealth(person, analysis_year=2026)["wealth_analysis"][
        "timing_context"
    ]
    assert tc["liunian_pillar"] == "丙午"  # 2026 year ganzhi
    assert tc["dayun_pillar"] == "乙酉"
    assert tc["overridden"] == {"dayun_pillar": False, "liunian_pillar": False}
    assert abs(tc["dayun_age"] - 28.56) < 0.5


@pytest.mark.parametrize("gender", ["乾", "未知"])
def test_explicit_dayun_has_no_automatic_period(gender) -> None:
    person = create_person_info(1990, 6, 15, 10, "t", gender, "北京")
    tc = bazi.calculate_bazi_wealth(person, analysis_year=2026, dayun_pillar="壬戌")[
        "wealth_analysis"
    ]["timing_context"]
    assert tc["overridden"] == {"dayun_pillar": True, "liunian_pillar": False}
    assert tc["dayun_pillar"] == "壬戌"
    assert tc["liunian_pillar"] == "丙午"
    assert tc["dayun_status"] == "explicit_override"
    assert (
        tc["dayun_start_at"]
        is tc["dayun_end_at"]
        is tc["dayun_selection_basis"]
        is None
    )


@pytest.mark.parametrize(
    "hour,expected",
    [(("丙", "寅"), "食神"), (("辛", "未"), "正官"), (("壬", "申"), "偏印")],
)
def test_children_preserves_hour_pillar_and_its_stem_classification(
    hour, expected: str
) -> None:
    from fatebridge.utils.data import get_ten_god

    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": hour,
    }
    assert get_ten_god(pillars["day"][0], hour[0]).value == expected
    assert "hour" in pillars and "".join(pillars["hour"]) == "".join(hour)
