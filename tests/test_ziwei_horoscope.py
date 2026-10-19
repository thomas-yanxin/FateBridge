from fatebridge.core.metaphysics.ziwei import (
    ZIWEI_SIHUA_RULES,
    build_ziwei_chart,
    build_ziwei_horoscope,
)
from fatebridge.services.metaphysics import _build_analysis_seed, _build_person_seed
from fatebridge.utils.birth_input import create_person_info

SCOPES = ["大限", "小限", "流年", "流月", "流日", "流时"]
BIRTH = dict(birth_year=1994, birth_month=8, birth_day=23, birth_hour=14, gender="男")
TARGET = dict(year=2026, month=6, day=19, hour=14)


def _horoscope_for(birth, target):
    person = create_person_info(**birth)
    natal_seed = _build_person_seed(person)
    chart = build_ziwei_chart(natal_seed, person.gender or "未知")
    target_seed = _build_analysis_seed(
        analysis_year=target["year"],
        analysis_month=target["month"],
        analysis_day=target["day"],
        analysis_hour=target["hour"],
    )
    return build_ziwei_horoscope(
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
    )


def test_horoscope_has_six_scopes_with_expected_shape():
    h = _horoscope_for(BIRTH, TARGET)
    assert h["engine"] == "fatebridge-offline"
    assert h["nominal_age"] == 2026 - 1994 + 1
    got = {s["scope"]: s for s in h["scopes"]}
    assert set(got) == set(SCOPES)
    for s in h["scopes"]:
        assert set(s.keys()) == {
            "scope",
            "palace_name",
            "scope_palace_role",
            "natal_palace_name",
            "mutagen_natal_links",
            "branch",
            "branch_index",
            "palace_ganzhi",
            "stem",
            "mutagen",
        }
        assert 0 <= s["branch_index"] <= 11
        assert set(s["mutagen"].keys()) == {"化禄", "化权", "化科", "化忌"}


def test_liunian_branch_matches_year_pillar_and_mutagen_from_year_stem():
    target_seed = _build_analysis_seed(
        analysis_year=2026, analysis_month=6, analysis_day=19, analysis_hour=14
    )
    year_stem, year_branch = target_seed.pillars["year"]
    h = _horoscope_for(BIRTH, TARGET)
    liunian = next(s for s in h["scopes"] if s["scope"] == "流年")
    assert liunian["branch"] == year_branch
    assert liunian["stem"] == year_stem
    assert liunian["mutagen"] == dict(ZIWEI_SIHUA_RULES[year_stem])


def test_daxian_palace_age_range_contains_nominal_age():
    person = create_person_info(**BIRTH)
    natal_seed = _build_person_seed(person)
    chart = build_ziwei_chart(natal_seed, "男")
    h = _horoscope_for(BIRTH, TARGET)
    daxian = next(s for s in h["scopes"] if s["scope"] == "大限")
    palace = next(p for p in chart["palaces"] if p["ganzhi"][1] == daxian["branch"])
    lo, hi = (int(x) for x in palace["daxian"].split("~"))
    assert lo <= h["nominal_age"] <= hi
