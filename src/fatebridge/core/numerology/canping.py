"""金锁银匙起数、命宫顺排与相对干支年序。

gu取数采用卷六所选规则，ming保留具名月支变法。条文资料由
canping_texts提供；这里的命宫运序不建立民用时刻区间，实际配运由
canping_timing处理。历史移植快照不作独立准确性参考。
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from fatebridge.core.numerology.canping_texts import (
    lookup_record,
    pair_resolution,
    selection_snapshot,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import get_nayin

BRANCHES: tuple[str, ...] = (
    "子",
    "丑",
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
)
BRANCH_NUM: dict[str, int] = {
    branch: index + 1 for index, branch in enumerate(BRANCHES)
}

# 明法（胖胖熊）：月支(月建/八字月支)反向取日宫支。
MONTH_TO_DAY_PALACE: dict[str, str] = {
    "寅": "亥",
    "卯": "戌",
    "辰": "酉",
    "巳": "申",
    "午": "未",
    "未": "午",
    "申": "巳",
    "酉": "辰",
    "戌": "卯",
    "亥": "寅",
    "子": "丑",
    "丑": "子",
}

# 水火 +27、土 +50、木金 +0。
ELEMENT_ADD: dict[str, int] = {"水": 27, "火": 27, "土": 50, "木": 0, "金": 0}
# 水1 火2 木3 金4 土5。
ELEMENT_PEI: dict[str, int] = {"水": 1, "火": 2, "木": 3, "金": 4, "土": 5}

PART_NAMES: dict[str, str] = {
    "水": "水部",
    "火": "火部",
    "木": "木部",
    "金": "金部",
    "土": "土部",
}

GANS: tuple[str, ...] = (
    "甲",
    "乙",
    "丙",
    "丁",
    "戊",
    "己",
    "庚",
    "辛",
    "壬",
    "癸",
)


class LegacyLuckStep(TypedDict):
    index: int
    branch: str
    ageStart: int
    ageEnd: int


def nayin_element(year_gz: str) -> str:
    """年干支 → 纳音五行（金/木/水/火/土）。

    Reuses FateBridge's get_nayin (matching horosa's NAYIN_ELEMENT over all 60
    ganzhi) and takes its last char.
    """
    cycle = {GANS[i % 10] + BRANCHES[i % 12] for i in range(60)}
    if not isinstance(year_gz, str) or year_gz not in cycle:
        return ""
    nayin = get_nayin(year_gz[0], year_gz[1])
    if not nayin or nayin == "未知纳音":
        return ""
    return nayin[-1]


def _branch_from_num(number: int) -> str:
    return BRANCHES[((number - 1) % 12 + 12) % 12]


def _branch_of(ganzhi_or_branch: str) -> str:
    text = ganzhi_or_branch or ""
    if len(text) >= 2 and text[1] in BRANCH_NUM:
        return text[1]
    if len(text) == 1 and text in BRANCH_NUM:
        return text
    return ""


def day_palace(month_branch: str, day_branch: str, method: str = "gu") -> str:
    """日宫支：明法用月支反向，古法直接用八字日支。"""
    if method == "gu":
        return day_branch
    elif method == "ming":
        return MONTH_TO_DAY_PALACE[month_branch]
    else:
        raise ValueError("method 仅支持 gu（原典日支）或 ming（月支变法）。")


def ming_gong(day_palace_branch: str, hour_branch: str) -> str:
    """命宫：日宫支配卯时起，逆数至生时。"""
    mao_branch_number = BRANCH_NUM["卯"]
    day_palace_number = BRANCH_NUM[day_palace_branch]
    hour_branch_number = BRANCH_NUM[hour_branch]
    ming_gong_number = (
        (day_palace_number - (hour_branch_number - mao_branch_number) - 1) % 12 + 12
    ) % 12 + 1
    return _branch_from_num(ming_gong_number)


def compute_number(day_branch: str, hour_branch: str, element: str) -> dict[str, int]:
    """Calculate the forward and reverse Canping lookup numbers."""
    if element not in ELEMENT_ADD:
        raise ValueError("纳音五行必须是水、火、木、金、土。")
    day_branch_number = BRANCH_NUM[day_branch]
    hour_branch_number = BRANCH_NUM[hour_branch]
    # note (canping): The volume six Metal example counts matching branches through a full cycle including both ends.
    forward_count = ((hour_branch_number - day_branch_number) % 12 or 12) + 1
    reverse_count = ((day_branch_number - hour_branch_number) % 12 or 12) + 1
    zi_origin_count = day_branch_number + hour_branch_number
    base_number = 2000 + zi_origin_count + ELEMENT_ADD[element] + ELEMENT_PEI[element]
    return {
        "shun": forward_count,
        "ni": reverse_count,
        "ziRound": zi_origin_count,
        "numShun": base_number + forward_count * 100,
        "numNi": base_number + reverse_count * 100,
    }


def _verses(element: str, numbers: dict[str, int], kind: str | None) -> dict[str, Any]:
    def status(text: str) -> str:
        if not text or all(c in "○〇□ \n，。" for c in text):
            return "unavailable_in_local_corpus"
        return (
            "incomplete_transcription"
            if any(c in text for c in "○〇□")
            else "unverified_transcription"
        )

    shun = lookup_record(element, numbers["numShun"], kind)
    ni = lookup_record(element, numbers["numNi"], kind)

    def selected_status(record: dict[str, Any]) -> str:
        state = record["selection"]["cell_status"]
        if state in {
            "source_cell_visually_collated",
            "source_printed_blank",
            "source_printed_partial_blank",
            "source_reading_uncertain",
            "not_selected_missing_gender",
        }:
            return str(state)
        return status(record["text"])

    return {
        "numShun": numbers["numShun"],
        "numNi": numbers["numNi"],
        "textShun": shun["text"],
        "textNi": ni["text"],
        "statusShun": selected_status(shun),
        "statusNi": selected_status(ni),
        "selectionShun": shun["selection"],
        "selectionNi": ni["selection"],
        "pair_resolution": pair_resolution(shun, ni),
    }


def _kind_for_gender(gender: str | None) -> Literal["male", "female"] | None:
    if gender is None:
        return None
    elif isinstance(gender, str):
        normalized_gender = normalize_gender(gender)
        if normalized_gender == "女":
            return "female"
        elif normalized_gender == "男":
            return "male"
    raise ValueError("参评本命选栏需要明确男／女；未提供时可算数，但不能默认性别。")


def dayun_sequence(
    day_palace_branch: str,
    hour_branch: str,
    qiyun_age: int = 1,
    count: int = 9,
) -> tuple[list[LegacyLuckStep], str]:
    """Generate the legacy decade sequence forward from the Ming Gong branch."""
    ming_gong_branch = ming_gong(day_palace_branch, hour_branch)
    first_branch_number = BRANCH_NUM[ming_gong_branch]
    steps: list[LegacyLuckStep] = []
    for step_index in range(count):
        branch = _branch_from_num(first_branch_number + step_index)
        start_age_years = qiyun_age + 10 * step_index
        steps.append(
            {
                "index": step_index,
                "branch": branch,
                "ageStart": start_age_years,
                "ageEnd": start_age_years + 9,
            }
        )
    return steps, ming_gong_branch


def _year_ganzhi(year: int) -> str:
    return GANS[((year - 4) % 10 + 10) % 10] + BRANCHES[((year - 4) % 12 + 12) % 12]


def calculate(
    *,
    year_gz: str,
    month_branch: str,
    day_branch: str,
    hour_branch: str,
    gender: str | None = None,
    method: str = "gu",
    qiyun_age: int = 1,
    liunian_branch: str | None = None,
    active_dayun_branch: str | None = None,
    include_luck: bool = True,
) -> dict[str, Any]:
    """本命 + 大运 (+ 可选单点流年) 起数与条文。"""
    kind_main = _kind_for_gender(gender)
    normalized_gender = (
        None if kind_main is None else ("女" if kind_main == "female" else "男")
    )
    element = nayin_element(year_gz)
    dp_branch = day_palace(month_branch, day_branch, method)

    benming = compute_number(dp_branch, hour_branch, element)
    benming_verses = _verses(element, benming, kind_main)

    luck_steps, ming_gong_branch = (
        dayun_sequence(dp_branch, hour_branch, qiyun_age) if include_luck else ([], "")
    )
    dayun: list[dict[str, Any]] = []
    for step in luck_steps:
        info = compute_number(dp_branch, step["branch"], element)
        dayun.append({**step, **info, "verses": _verses(element, info, "luck")})

    liunian: dict[str, Any] | None = None
    if liunian_branch:
        if active_dayun_branch is None or active_dayun_branch not in BRANCHES:
            raise ValueError("单点流年须明确active_dayun_branch，不能默认取第一运。")
        else:
            taisui_branch = _branch_of(liunian_branch)
            annual_numbers = compute_number(taisui_branch, active_dayun_branch, element)
            liunian = {
                "taisuiBranch": taisui_branch,
                "dayunBranch": active_dayun_branch,
                **annual_numbers,
                "verses": _verses(element, annual_numbers, "luck"),
            }

    return {
        "method": method,
        "gender": normalized_gender,
        "element": element,
        "partName": PART_NAMES.get(element, f"{element}部"),
        "fourPillars": {
            "yearGz": year_gz,
            "monthBranch": month_branch,
            "dayBranch": day_branch,
            "hourBranch": hour_branch,
        },
        "dayPalaceBranch": dp_branch,
        "mingGong": ming_gong_branch,
        "kindMain": kind_main,
        "benming": {**benming, "verses": benming_verses},
        "dayun": dayun,
        "liunian": liunian,
        "qiyunAge": qiyun_age if include_luck else None,
        "dayunPolicy": (
            "legacy_minggong_unverified_v1" if include_luck else "not_computed"
        ),
    }


def liunian_series(
    *,
    year_gz: str,
    month_branch: str,
    day_branch: str,
    hour_branch: str,
    gender: str | None = None,
    method: str = "gu",
    qiyun_age: int = 1,
    birth_year: int | None = None,
    start_age: int = 1,
    end_age: int = 120,
) -> dict[str, Any]:
    """按虚岁与实际大运支逐岁起数，起运前不生成编号或诗文。

    birth_year 为年柱对应的起始年标签；None 只推进相对干支年序，不映射UTC区间。
    """
    if (
        type(start_age) is not int
        or type(end_age) is not int
        or start_age < 1
        or end_age < start_age
    ):
        raise ValueError("年序年龄范围须为从1起的有序整数。")
    if type(qiyun_age) is not int or qiyun_age < 0:
        raise ValueError("起运年龄须为明确的非负整数。")
    if birth_year is not None and (type(birth_year) is not int or birth_year < 1):
        raise ValueError("公历年标签须为正整数；未知用None，不能用布尔值代替。")
    if birth_year is not None and _year_ganzhi(birth_year) != year_gz:
        raise ValueError("流年起始年标签须与出生年柱一致；立春前不能直接用公历出生年。")
    result = calculate(
        year_gz=year_gz,
        month_branch=month_branch,
        day_branch=day_branch,
        hour_branch=hour_branch,
        gender=gender,
        method=method,
        qiyun_age=qiyun_age,
        include_luck=False,
    )
    element = result["element"]
    # 年干支本身足以确定相对太岁。公历纪年未知不能退回出生日支，
    # 也不能从六十年循环任意选择一个公历甲子年。
    cycle = tuple(GANS[i % 10] + BRANCHES[i % 12] for i in range(60))
    birth_cycle_index = cycle.index(year_gz)
    # 不将九步以后的流年钳制在最后一运；按请求年龄实际展开。
    count = max(9, (end_age - qiyun_age) // 10 + 1)
    sequence, _ = dayun_sequence(
        result["dayPalaceBranch"], hour_branch, qiyun_age, count
    )
    dayun: list[dict[str, Any]] = []
    for step in sequence:
        info = compute_number(result["dayPalaceBranch"], step["branch"], element)
        dayun.append({**step, **info, "verses": _verses(element, info, "luck")})

    def dayun_at(age: int) -> dict[str, Any] | None:
        k = (age - qiyun_age) // 10
        if k < 0:
            return None
        return dayun[k]

    rows: list[dict[str, Any]] = []
    for age in range(start_age, end_age + 1):
        year = birth_year + age - 1 if birth_year is not None else None
        ganzhi = cycle[(birth_cycle_index + age - 1) % 60]
        taisui = ganzhi[1]
        row: dict[str, Any] = {
            "age": age,
            "year": year,
            "ganzhi": ganzhi,
            "taisuiBranch": taisui,
        }
        dy = dayun_at(age)
        if dy is None:
            rows.append({**row, "status": "not_started"})
            continue
        info = compute_number(taisui, dy["branch"], element)
        row.update(
            {
                "status": "active",
                "dayunBranch": dy["branch"],
                "dayunRange": f"{dy['ageStart']}-{dy['ageEnd']}",
                **info,
                "verses": _verses(element, info, "luck"),
            }
        )
        rows.append(row)
    return {
        "element": element,
        "partName": result["partName"],
        "dayun": dayun,
        "rows": rows,
        "qiyunAge": qiyun_age,
        "birth_pillar_year": birth_year,
        "year_boundary": (
            "provided_year_labels_only"
            if birth_year is not None
            else "relative_ganzhi_year_labels_only"
        ),
        "age_policy": "relative_sexagenary_year_ordinal; no_actual_boundaries",
    }


def build_snapshot_text(result: dict[str, Any]) -> str:
    """渲染 [起盘]/[本命]/[大运·歲運]/[流年·歲運] 四段中文快照。"""
    if not result:
        return ""
    lines: list[str] = []
    benming = result.get("benming") or {}
    verses = benming.get("verses") or {}
    method_label = "古法(八字日支)" if result["method"] == "gu" else "明法(月支反向)"

    lines.append("[起盘]")
    lines.append(
        f"年纳音：{result['element']}（{result['partName']}）  取法：{method_label}"
    )
    if result.get("mingGong"):
        lines.append(f"日宫支：{result['dayPalaceBranch']}  命宫：{result['mingGong']}")
    else:
        lines.append(f"日宫支：{result['dayPalaceBranch']}")
    if result.get("timing"):
        lines.append(
            f"配运政策：{result['timing']['profile_id']}（与河洛六九年大限区分）"
        )
    lines.append("")
    lines.append("[本命]")
    if result.get("kindMain") is None:
        lines.append("未提供计算性别；保留两数，本命未选择男／女栏目。")
    lines.append(f"顺 {verses.get('numShun')}：{verses.get('textShun')}")
    lines.append(f"逆 {verses.get('numNi')}：{verses.get('textNi')}")
    lines.append("")
    lines.append("[大运·歲運]")
    for step in result.get("dayun") or []:
        step_verses = step.get("verses") or {}
        interval = (
            f"[{step['start_at']}, {step['end_at']}) {step['pillar']}"
            if "start_at" in step
            else f"{step['ageStart']}-{step['ageEnd']}岁 {step['branch']}"
        )
        lines.append(
            f"{interval}："
            f"顺{step_verses.get('numShun')} {step_verses.get('textShun')} ／ "
            f"逆{step_verses.get('numNi')} {step_verses.get('textNi')}"
        )
    selected = (result.get("timing") or {}).get("selected")
    if selected:
        lines += ["", f"[查询时刻·{selected['at']}]", f"立春年柱：{selected['ganzhi']}"]
        if selected["status"] == "not_started":
            lines.append("尚未起运；不取第一运代替，未生成当段流年数或岁运条文。")
        else:
            verses = selected["verses"]
            lines.append(
                f"大运{selected['dayun_pillar']}：顺{selected['numShun']} {verses['textShun']} ／ "
                f"逆{selected['numNi']} {verses['textNi']}"
            )
    liunian = result.get("liunian")
    if liunian:
        lv = liunian.get("verses") or {}
        lines.append("")
        lines.append("[流年·歲運]")
        lines.append(
            f"太岁{liunian['taisuiBranch']}/大运{liunian['dayunBranch']}："
            f"顺{lv.get('numShun')} {lv.get('textShun')} ／ "
            f"逆{lv.get('numNi')} {lv.get('textNi')}"
        )
    lines.extend(
        ["", "[参评选条与来源]", selection_snapshot(benming.get("verses") or {})]
    )
    if selected and selected["status"] == "active":
        lines.append("查询当段：" + selection_snapshot(selected["verses"]))
    return "\n".join(lines)
