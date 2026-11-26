"""Pure structural checks for 36 classical Ziwei patterns without None stubs."""

import pytest

from fatebridge.core.ziwei.calendar import build_ziwei_analysis_seed
from fatebridge.core.ziwei.chart import build_ziwei_chart, build_ziwei_rules


def _seed(year, month, day, hour):
    return build_ziwei_analysis_seed(
        analysis_year=year, analysis_month=month, analysis_day=day, analysis_hour=hour
    )


def _matched_ids(chart) -> set[str]:
    return {row["id"] for row in chart["named_patterns"]["matched"]}


def test_classical_pattern_catalogue_has_at_least_30_rules_and_no_none_stubs() -> None:
    catalogue = build_ziwei_rules()["rule_catalogue"]["named_patterns"]
    assert catalogue["count"] >= 36
    assert len(catalogue["rules"]) >= 36

    chart = build_ziwei_chart(_seed(1990, 5, 15, 10), "男")
    patterns = chart["named_patterns"]
    assert patterns["total_checked"] >= 36
    for row in patterns["matched"]:
        assert row["matched"] is True
        assert all(isinstance(v, bool) for v in row["conditions"].values())


@pytest.mark.parametrize(
    "birth,expected_met",
    [
        ((2023, 1, 31, 22), True),
        ((2023, 1, 31, 6), True),
        ((2023, 1, 22, 18), False),
    ],
)
def test_ri_chu_fu_sang_only_matches_sun_in_mao_ming_or_career(
    birth, expected_met
) -> None:
    chart = build_ziwei_chart(_seed(*birth), "男")
    assert ("ri_chu_fu_sang" in _matched_ids(chart)) is expected_met


def test_yue_luo_hai_gong_wu_qu_shou_yuan_and_ri_yue_zhao_bi() -> None:
    moon_chart = build_ziwei_chart(_seed(2023, 1, 31, 6), "男")
    assert moon_chart["ming_gong"]["branch"] == "亥"
    assert "yue_luo_hai_gong" in _matched_ids(moon_chart)

    wu_in_mao = build_ziwei_chart(_seed(2023, 2, 2, 22), "男")
    assert wu_in_mao["ming_gong"]["branch"] == "卯"
    assert "wu_qu_shou_yuan" not in _matched_ids(wu_in_mao)

    wu_elsewhere = build_ziwei_chart(_seed(2023, 1, 23, 4), "男")
    assert "wu_qu_shou_yuan" in _matched_ids(wu_elsewhere)

    property_chart = build_ziwei_chart(_seed(2023, 1, 27, 8), "男")
    assert "ri_yue_zhao_bi" in _matched_ids(property_chart)


def test_jun_chen_qing_hui_and_quan_lu_sheng_feng() -> None:
    met_chart = build_ziwei_chart(_seed(2023, 5, 26, 20), "男")
    assert "jun_chen_qing_hui" in _matched_ids(met_chart)

    opp_chart = build_ziwei_chart(_seed(2023, 1, 24, 20), "男")
    assert "jun_chen_qing_hui" not in _matched_ids(opp_chart)

    quan_lu_met = build_ziwei_chart(_seed(2019, 2, 6, 14), "男")
    assert "quan_lu_sheng_feng" in _matched_ids(quan_lu_met)

    quan_lu_xian = build_ziwei_chart(_seed(2024, 2, 12, 22), "男")
    assert "quan_lu_sheng_feng" not in _matched_ids(quan_lu_xian)


def test_flanking_and_empty_ming_borrowed_opposite_stars() -> None:
    sun_moon_flank = build_ziwei_chart(_seed(2023, 1, 22, 14), "男")
    assert "ri_yue_jia_ming" in _matched_ids(sun_moon_flank)

    chang_qu = build_ziwei_chart(_seed(1990, 9, 28, 4), "男")
    assert "chang_qu_jia_ming" in _matched_ids(chang_qu)

    empty_chart = build_ziwei_chart(_seed(1992, 8, 15, 14), "男")
    matched = {row["id"]: row for row in empty_chart["named_patterns"]["matched"]}
    if "ming_wu_zheng_yao" in matched:
        assert matched["ming_wu_zheng_yao"]["borrowed_opposite_palace"] == "迁移宫"
        assert isinstance(
            matched["ming_wu_zheng_yao"]["borrowed_opposite_major_stars"], list
        )
