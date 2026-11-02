"""Classical 子平 lookups (月令取格 / 十二长生 / 调候) — deterministic facts.

These lock in the table-driven algorithms merged from the 八字/ 格局·调候 corpus.
They assert computation only, never interpretation.
"""

from fatebridge.core.classical import (
    build_classical_overview,
    determine_monthly_structure,
    seasonal_climate_god,
    twelve_life_stage,
)
from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.utils.birth_input import PersonInfo

# --- 十二长生 --------------------------------------------------------------- #


def test_twelve_life_stage_yang_stem_forward():
    # 甲(阳木)顺行：长生亥 → 临官寅 → 帝旺卯
    assert twelve_life_stage("甲", "亥") == "长生"
    assert twelve_life_stage("甲", "寅") == "临官"
    assert twelve_life_stage("甲", "卯") == "帝旺"
    assert twelve_life_stage("甲", "午") == "死"


def test_twelve_life_stage_yin_stem_reverse():
    # 乙(阴木)逆行：长生午 → 帝旺寅
    assert twelve_life_stage("乙", "午") == "长生"
    assert twelve_life_stage("乙", "寅") == "帝旺"
    # 癸(阴水)逆行：长生卯
    assert twelve_life_stage("癸", "卯") == "长生"


# --- 月令取格 --------------------------------------------------------------- #


def test_monthly_structure_benqi_when_not_transparent():
    # 辛日主、午月：本气丁为七杀，无透 → 七杀格（本气取格）
    pillars = {
        "year": ("庚", "午"),
        "month": ("壬", "午"),
        "day": ("辛", "酉"),
        "hour": ("戊", "子"),
    }
    structure = determine_monthly_structure(pillars, "辛")
    assert structure["label"] == "七杀格"
    assert structure["structure_god"]["role"] == "本气"
    assert structure["is_special"] is False


def test_monthly_structure_prefers_transparent_hidden_stem():
    # 甲日主、辰月（藏戊乙癸）：癸(余气,正印)透年干 → 取正印格而非本气偏财格
    pillars = {
        "year": ("癸", "卯"),
        "month": ("丙", "辰"),
        "day": ("甲", "子"),
        "hour": ("乙", "亥"),
    }
    structure = determine_monthly_structure(pillars, "甲")
    assert structure["label"] == "正印格"
    assert structure["structure_god"]["stem"] == "癸"
    assert structure["structure_god"]["transparent"] is True


def test_monthly_structure_lu_blade_special():
    # 甲日主、寅月：本气甲为比肩 → 建禄格，标记 is_special
    pillars = {
        "year": ("丙", "寅"),
        "month": ("庚", "寅"),
        "day": ("甲", "子"),
        "hour": ("乙", "亥"),
    }
    structure = determine_monthly_structure(pillars, "甲")
    assert structure["label"] == "建禄格"
    assert structure["is_special"] is True


# --- 调候用神 --------------------------------------------------------------- #


def test_seasonal_climate_known_entry():
    # 甲木生午月：调候用神 癸（主），丁/庚（辅）
    climate = seasonal_climate_god("甲", "午")
    assert climate["available"] is True
    assert climate["primary"] == "癸"
    assert climate["secondary"] == ["丁", "庚"]


def test_seasonal_climate_table_complete():
    # 全 10 干 × 12 月支均有调候表项（120 格无缺漏）
    stems = list("甲乙丙丁戊己庚辛壬癸")
    branches = list("子丑寅卯辰巳午未申酉戌亥")
    for stem in stems:
        for branch in branches:
            assert seasonal_climate_god(stem, branch)["available"], (stem, branch)


# --- overview + 集成 -------------------------------------------------------- #


def test_build_classical_overview_shape():
    pillars = {
        "year": ("庚", "午"),
        "month": ("壬", "午"),
        "day": ("甲", "子"),
        "hour": ("丙", "寅"),
    }
    overview = build_classical_overview(pillars)
    assert set(overview) == {
        "monthly_structure",
        "seasonal_climate",
        "life_stages",
        "root_profile",
    }
    assert overview["root_profile"]["global_strength_status"] == "not_adjudicated"
    assert overview["life_stages"]["per_pillar"]["时支"] == "临官"


def test_chart_exposes_classical_facts_and_snapshot_section():
    person = PersonInfo(
        name="测试",
        birth_year=1990,
        birth_month=6,
        birth_day=15,
        birth_hour=14,
        birth_minute=0,
        gender="男",
    )
    result = calculate_bazi_birth(person)
    assert "classical" in result["bazi_birth"]
    assert result["bazi_birth"]["classical"]["monthly_structure"]["label"].endswith(
        "格"
    )
    assert "[格局调候]" in result["snapshot_text"]
