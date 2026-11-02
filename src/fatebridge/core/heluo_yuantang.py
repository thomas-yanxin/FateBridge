"""Source-specific Yuantang placement, with no guessed solstice half-year.

NLC Wenming Shuju printing, PDF 26-31: repeat matching lines only when
there are at most three, then borrow opposite lines; pure Qian/Kun have their
own sex/half-year directions. Month-pillar Zi/Wu alone cannot resolve a half.
"""

from typing import Any, Optional

from fatebridge.core.heluo_seasonal import SOURCE_SHA256, SOURCE_URL

RULESET_ID = "heluo_yuantang_nlc_v1"
YANG_HOURS = list("子丑寅卯辰巳")
YIN_HOURS = list("午未申酉戌亥")
PURE_HOUR_TO_YAO = dict(
    zip(YANG_HOURS + YIN_HOURS, [1, 2, 3, 1, 2, 3, 4, 5, 6, 4, 5, 6])
)


def resolve_half_year(
    month_zhi: str, explicit: Optional[bool]
) -> tuple[Optional[bool], str]:
    """A sexagenary month pillar spans its Jie boundaries, not a solstice."""
    if month_zhi not in YANG_HOURS + YIN_HOURS:
        raise ValueError("月支须为十二地支。")
    if explicit is not None:
        if type(explicit) is not bool:
            raise ValueError("阴阳令须为布尔值，不能以字符串或数字代替。")
        return explicit, "explicit_half_year"
    if month_zhi in {"子", "午"}:
        return None, "boundary_month_unresolved"
    return month_zhi in "丑寅卯辰巳", "month_branch_half_year"


def placement(
    lines: list[int], hour_zhi: str, is_male: bool, yang_ling: Optional[bool]
) -> dict[str, Any]:
    if (
        not isinstance(lines, list)
        or len(lines) != 6
        or any(type(b) is not int or b not in (0, 1) for b in lines)
    ):
        raise ValueError("元堂须输入自初至上的六个0/1整数。")
    if hour_zhi not in YANG_HOURS + YIN_HOURS:
        raise ValueError("元堂时支须为十二地支。")
    if type(is_male) is not bool or (
        yang_ling is not None and type(yang_ling) is not bool
    ):
        raise ValueError("元堂性别标志及阴阳令不得隐式强转。")
    yang_hour = hour_zhi in YANG_HOURS
    hours = YANG_HOURS if yang_hour else YIN_HOURS
    matching = [p for p, bit in enumerate(lines, 1) if bit == int(yang_hour)]
    other = [p for p in range(1, 7) if p not in matching]
    count = len(matching)
    direction = None
    if count in (0, 6):
        qian = lines[0] == 1
        needs_half = (qian and not is_male) or (not qian and is_male)
        if needs_half and yang_ling is None:
            raise ValueError("纯乾女命或纯坤男命的元堂须明确至点阴阳令。")
        reverse = (qian and not is_male and yang_ling is True) or (
            not qian and is_male and yang_ling is False
        )
        slots = [
            7 - PURE_HOUR_TO_YAO[h] if reverse else PURE_HOUR_TO_YAO[h] for h in hours
        ]
        direction = "descending" if reverse else "ascending"
        rule = "pure_qian" if qian else "pure_kun"
        pages = [30, 31] if qian else [31]
    else:
        slots = (matching + matching + other if count <= 3 else matching + other)[:6]
        rule = (
            "repeat_matching_then_borrow" if count <= 3 else "matching_once_then_borrow"
        )
        pages = {
            (True, 1): [26, 27],
            (False, 1): [27],
            (True, 2): [27],
            (False, 2): [28],
            (True, 3): [28],
            (False, 3): [28, 29],
            (True, 4): [29],
            (False, 4): [29],
            (True, 5): [29, 30],
            (False, 5): [30],
        }[(yang_hour, count)]
    index = hours.index(hour_zhi)
    return {
        "rule_id": rule,
        "hour_zhi": hour_zhi,
        "hour_half": "yang" if yang_hour else "yin",
        "hour_index": index + 1,
        "matching_positions": matching,
        "other_positions": other,
        "slot_positions": slots,
        "selected_pos": slots[index],
        "pure_direction": direction,
        "source_pdf_pages": pages,
    }


def source_profile() -> dict[str, Any]:
    return {
        "ruleset_id": RULESET_ID,
        "version": "1.0.0",
        "source_url": SOURCE_URL,
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_pages": list(range(26, 33)),
        "review_status": "single_visual_collation; independent_second_review_pending",
    }


def derivation_snapshot(evidence: dict[str, Any]) -> str:
    half = evidence["half_year"]
    layout = evidence["placement"]
    if half["value"] is None:
        half_text = "至点半年未定；两个半年所得元堂和后天卦相同，保留可唯一计算结果"
    else:
        half_text = (
            "阳令（冬至至夏至）" if half["value"] else "阴令（夏至至冬至）"
        ) + f"；来源{half['basis']}"
    pages = "、".join(map(str, layout["source_pdf_pages"]))
    direction = (
        "；纯卦自上而下"
        if layout["pure_direction"] == "descending"
        else "；纯卦自下而上" if layout["pure_direction"] == "ascending" else ""
    )
    comparison = "；".join(
        f"{'阳' if c['yang_ling'] else '阴'}令：元堂{c['xian_yuan']}爻→{c['hou_name']}{c['hou_yuan']}爻"
        for c in half["counterfactuals"]
    )
    move = (
        "交换上下卦"
        if evidence["houtian_transform"]["swap_trigrams"]
        else "三至尊变而不易，上下卦不交换"
    )
    return "\n".join(
        [
            "[元堂起例与阴阳令]",
            f"{evidence['gender']}命；" + half_text + "。",
            f"{layout['hour_zhi']}时属于{'子至巳阳' if layout['hour_half']=='yang' else '午至亥阴'}时组第{layout['hour_index']}位{direction}；依次爻位{layout['slot_positions']}，实际取{layout['selected_pos']}爻（PDF第{pages}页）。",
            f"所取元堂爻先变，随后{move}；后天元堂{evidence['houtian_transform']['resulting_yuan']}爻。",
            "半年反事实比较（非两个实际出生时刻）：" + comparison + "。",
            "元堂定位不等于完整得体或葉否；图式单次目校，待独立复核。",
        ]
    )
