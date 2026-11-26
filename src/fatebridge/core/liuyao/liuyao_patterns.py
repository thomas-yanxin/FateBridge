"""Detect Liuyao clash, harmony and active reversal patterns."""

from typing import Any

from fatebridge.utils.data import BRANCH_CONFLICTS

LIUCHONG_HEXAGRAM_CODES = frozenset(
    {
        "111111",  # 乾为天
        "000000",  # 坤为地
        "100100",  # 震为雷
        "011011",  # 巽为风
        "010010",  # 坎为水
        "101101",  # 离为火
        "001001",  # 艮为山
        "110110",  # 兑为泽
        "100111",  # 天雷无妄
        "111100",  # 雷天大壮
    }
)


LIUHE_HEXAGRAM_CODES = frozenset(
    {
        "111000",  # 地天泰
        "000111",  # 天地否
        "000100",  # 雷地豫
        "100000",  # 地雷复
        "010110",  # 泽水困
        "110010",  # 水泽节
        "001101",  # 火山旅
        "101001",  # 山火贲
    }
)


def detect_sixyao_patterns(
    current_code: str,
    changed_code: str,
    current_branches: list[str],
    changed_branches: list[str],
    moving_indices: list[int],
    fanfu: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """识别六爻常见格局：六冲/六合/反吟/伏吟。"""
    patterns: list[dict[str, str]] = []
    # 本卦六冲 / 六合
    if current_code in LIUCHONG_HEXAGRAM_CODES:
        patterns.append(
            {"name": "本卦六冲", "basis": "本卦属十个六冲卦：八纯卦及无妄、大壮。"}
        )
    if current_code in LIUHE_HEXAGRAM_CODES:
        patterns.append({"name": "本卦六合", "basis": "本卦为六合卦。"})
    # 之卦六冲 / 六合
    if current_code != changed_code:
        if changed_code in LIUCHONG_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六冲", "basis": "之卦转为六冲。"})
        if changed_code in LIUHE_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六合", "basis": "之卦归六合。"})

    # 伏吟 / 反吟 (只在动爻上判断, 避开 changed_branch 为空的静爻)
    fu_count = 0
    fan_count = 0
    for idx in moving_indices:
        if idx < 0 or idx >= 6:
            continue
        orig_branch = current_branches[idx]
        new_branch = changed_branches[idx]
        if not orig_branch or not new_branch:
            continue
        if orig_branch == new_branch:
            fu_count += 1
        elif BRANCH_CONFLICTS.get(orig_branch) == new_branch:
            fan_count += 1
    if fu_count and fu_count == len(moving_indices):
        patterns.append(
            {
                "name": "伏吟",
                "basis": "仅实际动爻的纳支均保持相同；动爻仍是动爻，不代表卦未变。",
            }
        )
    elif fu_count:
        patterns.append(
            {
                "name": "局部伏吟",
                "basis": f"{fu_count}个动爻之支与原支相同。",
            }
        )
    if fan_count and fan_count == len(moving_indices):
        patterns.append(
            {
                "name": "反吟",
                "basis": "仅实际动爻的变支均与本支相冲；内外卦盘与卦体另查反伏证据。",
            }
        )
    elif fan_count:
        patterns.append(
            {
                "name": "局部反吟",
                "basis": f"{fan_count}个动爻之支与原支相冲。",
            }
        )

    if fanfu:
        if fanfu["explicit_body_example"]:
            body = fanfu["explicit_body_example"]
            patterns.append({"name": "卦体" + body["kind"], "basis": body["basis"]})
        for region in fanfu["regions"]:
            if region["nazhi_relation"] in ("反吟", "伏吟"):
                label = "内卦" if region["region"] == "inner" else "外卦"
                patterns.append(
                    {
                        "name": label + "纳支" + region["nazhi_relation"],
                        "basis": "该经卦已变，三爻卦盘纳支"
                        + ("相冲" if region["nazhi_relation"] == "反吟" else "相同")
                        + "；静爻位置只作卦盘比较，不新增变爻作用。",
                    }
                )

    return {
        "patterns": patterns,
        "is_liuchong_base": current_code in LIUCHONG_HEXAGRAM_CODES,
        "is_liuhe_base": current_code in LIUHE_HEXAGRAM_CODES,
        "is_liuchong_changed": current_code != changed_code
        and changed_code in LIUCHONG_HEXAGRAM_CODES,
        "is_liuhe_changed": current_code != changed_code
        and changed_code in LIUHE_HEXAGRAM_CODES,
    }
