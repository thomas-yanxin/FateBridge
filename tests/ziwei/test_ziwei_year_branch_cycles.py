"""Year-branch placement and public evidence for the two twelve-star cycles."""

import pytest

from fatebridge.core.ziwei.ziwei_cycle_sources import year_branch_cycles
from tests.support.transports import SPECS, projected_outputs, rest

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SUIQIAN = "岁建 晦气 丧门 贯索 官符 小耗 大耗 龙德 白虎 天德 吊客 病符".split()
JIANGQIAN = "将星 攀鞍 岁驿 息神 华盖 劫煞 灾煞 天煞 指背 咸池 月煞 亡神".split()
BIRTH = {
    "birth_year": 1992,
    "birth_month": 8,
    "birth_day": 15,
    "birth_hour": 14,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "gender": "男",
    "use_true_solar_time": False,
}
TARGET = {
    "analysis_year": 2027,
    "analysis_month": 6,
    "analysis_day": 15,
    "analysis_hour": 12,
    "analysis_minute": 37,
    "analysis_timezone": "UTC",
}


@pytest.mark.parametrize(
    "year_branch,jiang_branches",
    [(branch, "子丑寅卯辰巳午未申酉戌亥") for branch in "申子辰"]
    + [(branch, "酉戌亥子丑寅卯辰巳午未申") for branch in "巳酉丑"]
    + [(branch, "午未申酉戌亥子丑寅卯辰巳") for branch in "寅午戌"]
    + [(branch, "卯辰巳午未申酉戌亥子丑寅") for branch in "亥卯未"],
)
def test_all_year_branches_and_triad_starts(year_branch, jiang_branches):
    cycles = year_branch_cycles(year_branch, anchor_basis="natal_lunar_year_branch")
    assert cycles["year_branch"] == year_branch
    assert cycles["direction"] == "forward"
    assert cycles["suiqian"]["start_branch"] == year_branch
    assert cycles["jiangqian"]["start_branch"] == jiang_branches[0]
    year_index = BRANCHES.index(year_branch)
    sui_branches = BRANCHES[year_index:] + BRANCHES[:year_index]
    assert [(p["name"], p["branch"]) for p in cycles["suiqian"]["positions"]] == list(
        zip(SUIQIAN, sui_branches, strict=True)
    )
    assert [(p["name"], p["branch"]) for p in cycles["jiangqian"]["positions"]] == list(
        zip(JIANGQIAN, jiang_branches, strict=True)
    )


def test_annual_cycle_and_flowing_basis_match_three_surfaces(rest, tmp_path, capsys):
    fields = [
        "ziwei_horoscope.annual_cycles",
        "ziwei_horoscope.scopes",
    ]
    replies = projected_outputs(
        SPECS["ziwei_timing"], BIRTH | TARGET, fields, rest, tmp_path, capsys
    )
    timing = [reply["ziwei_horoscope"] for reply in replies]
    assert timing[0] == timing[1] == timing[2]
    annual = timing[0]["annual_cycles"]
    assert annual["anchor_basis"] == "target_lunar_year_branch"
    assert annual["year_branch"] == "未"
    assert len(annual["jiangqian"]["positions"]) == 12
    year = next(s for s in timing[0]["scopes"] if s["scope"] == "流年")
    assert year["flowing_star_basis"] == {
        "stem": "丁",
        "branch": "未",
        "branch_origin": "target_lunar_year_pillar",
    }
