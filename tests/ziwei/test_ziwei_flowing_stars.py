"""Flow-star placements and public delivery for the versioned Ziwei convention."""

import pytest

from fatebridge.core.ziwei.ziwei_auxiliary import flowing_horoscope_stars
from fatebridge.services.metaphysics import calculate_ziwei_horoscope
from fatebridge.utils.birth_input import create_person_info

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_STARS = ("天魁", "天钺", "文昌", "文曲", "禄存", "擎羊", "陀罗")
BRANCH_STARS = ("天马", "红鸾", "天喜", "年解")
# Read from iztro 2.5.8 src/star/location.ts, converted to Earthly Branch names.
# Each row is a complete, independent expected placement for one supplied input.
STEM_ROWS = dict(
    zip(
        "甲乙丙丁戊己庚辛壬癸",
        (
            "丑未巳酉寅卯丑",
            "子申午申卯辰寅",
            "亥酉申午巳午辰",
            "亥酉酉巳午未巳",
            "丑未申午巳午辰",
            "子申酉巳午未巳",
            "丑未亥卯申酉未",
            "午寅子寅酉戌申",
            "卯巳寅子亥子戌",
            "卯巳卯亥子丑亥",
        ),
    )
)
BRANCH_ROWS = dict(
    zip(
        BRANCHES,
        (
            "寅卯酉戌",
            "亥寅申酉",
            "申丑未申",
            "巳子午未",
            "寅亥巳午",
            "亥戌辰巳",
            "申酉卯辰",
            "巳申寅卯",
            "寅未丑寅",
            "亥午子丑",
            "申巳亥子",
            "巳辰戌亥",
        ),
    )
)
BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    gender="男",
    use_true_solar_time=False,
)
TARGET = dict(
    analysis_year=2027,
    analysis_month=6,
    analysis_day=15,
    analysis_hour=12,
    analysis_minute=37,
    analysis_timezone="UTC",
)


def expected_positions(stem, branch, *, annual=False):
    stars = STEM_STARS + BRANCH_STARS
    values = STEM_ROWS[stem] + BRANCH_ROWS[branch]
    if not annual:
        values = values[:-1]
    return dict(zip(stars, values))


def actual_positions(scope):
    rows = scope["flowing_stars"]
    positions = {row["star"]: row["branch"] for row in rows}
    assert len(positions) == len(rows)
    return positions


def test_pinned_software_formula_for_all_ten_stems_and_twelve_branches():
    palaces = [
        {
            "branch": b,
            "scope_palace_name": "scope-" + b,
            "natal_palace_name": "natal-" + b,
        }
        for b in BRANCHES
    ]
    for stem in STEM_ROWS:
        for branch in BRANCH_ROWS:
            rows = flowing_horoscope_stars(
                palaces, scope="流年", stem=stem, pillar_branch=branch
            )
            assert actual_positions({"flowing_stars": rows}) == expected_positions(
                stem, branch, annual=True
            )
            for row in rows:
                if row["star"] in STEM_STARS:
                    assert row["stem"] == stem and "basis_branch" not in row
                else:
                    assert row["basis_branch"] == branch and "stem" not in row
                assert row["scope_palace_name"] == "scope-" + row["branch"]
                assert row["natal_palace_name"] == "natal-" + row["branch"]
                assert row["natal_stars_relocated"] is False


def test_active_layers_use_own_calendar_pillars_even_when_ming_palace_differs():
    result = calculate_ziwei_horoscope(create_person_info(**BIRTH), **TARGET)
    scopes = {s["scope"]: s for s in result["ziwei_horoscope"]["scopes"]}
    assert "flowing_stars" not in scopes["小限"]
    assert "flowing_star_basis" not in scopes["小限"]
    for layer, stem, branch, ming, origin in (
        ("大限", "甲", "辰", "辰", "decadal_palace"),
        ("流年", "丁", "未", "未", "target_lunar_year_pillar"),
        ("流月", "丙", "午", "子", "target_effective_lunar_month_pillar"),
        ("流日", "乙", "丑", "戌", "target_day_pillar"),
        ("流时", "壬", "午", "辰", "target_hour_pillar"),
    ):
        scope = scopes[layer]
        basis = scope["flowing_star_basis"]
        assert (basis["stem"], basis["branch"], basis["branch_origin"]) == (
            stem,
            branch,
            origin,
        )
        assert scope["branch"] == ming
        assert actual_positions(scope) == expected_positions(
            stem, branch, annual=layer == "流年"
        )
        mapped = {p["branch"]: p for p in scope["palace_map"]}
        for row in scope["flowing_stars"]:
            assert row["scope"] == layer
            assert (
                row["scope_palace_name"] == mapped[row["branch"]]["scope_palace_name"]
            )
            assert (
                row["natal_palace_name"] == mapped[row["branch"]]["natal_palace_name"]
            )
    monthly = scopes["流月"]
    assert actual_positions(monthly)["天马"] == "申"
    assert BRANCH_ROWS[monthly["branch"]][0] == "寅"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize(
    "hour,day_divide,lunar_day,effective,software_normal,software_exact,actual,day_pillar,hour_pillar",
    [
        (12, "current", 15, 2, "乙卯", "丙辰", "乙卯", "癸巳", "戊午"),
        (23, "current", 15, 2, "乙卯", "丙辰", "乙卯", "癸巳", "壬子"),
        (23, "forward", 16, 3, "乙卯", "丙辰", "丙辰", "甲午", "甲子"),
    ],
)
def test_leap_month_and_late_zi_calendar_comparison(
    profile,
    hour,
    day_divide,
    lunar_day,
    effective,
    software_normal,
    software_exact,
    actual,
    day_pillar,
    hour_pillar,
):
    # 2023-04-05 is leap month two, day 15. Qingming (section start for 辰)
    # is before noon local time. iztro 2.5.8 + lunar-lite 0.2.8 uses the
    # original civil date for the monthly pillar even when timeIndex=12 rolls
    # the day pillar. Its exact configuration uses the solar month instead.
    result = calculate_ziwei_horoscope(
        create_person_info(**BIRTH),
        analysis_year=2023,
        analysis_month=4,
        analysis_day=5,
        analysis_hour=hour,
        analysis_minute=37,
        analysis_timezone="Asia/Shanghai",
        rule_profile=profile,
        day_divide=day_divide,
    )
    scopes = {s["scope"]: s for s in result["ziwei_horoscope"]["scopes"]}
    monthly = scopes["流月"]
    basis = monthly["flowing_star_basis"]
    assert basis["lunar_date"] == dict(
        year=2023, month=2, day=lunar_day, is_leap_month=True
    )
    assert basis["effective_lunar_month"] == effective
    assert basis["stem"] + basis["branch"] == actual
    positions = actual_positions(monthly)
    assert positions == expected_positions(*actual)
    assert (positions == expected_positions(*software_normal)) is (
        actual == software_normal
    )
    assert (positions == expected_positions(*software_exact)) is (
        actual == software_exact
    )
    assert actual_positions(scopes["流日"]) == expected_positions(*day_pillar)
    assert actual_positions(scopes["流时"]) == expected_positions(*hour_pillar)
