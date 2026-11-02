"""邵子参评数 / 金锁银匙 (canping) — 原生离线计算。

This is a native Python port of horosa's ``canpingLocal.js`` (邵子参评数 /
金锁银匙). canping is a "原生·非 kentang" technique: unlike qimen/taiyi/jinkou
(computed by a backend and only formatted), canping is computed entirely
in-process. The four pillars come from FateBridge's own calendar engine; this
module does the 金锁银匙 起数 + 条文查表. The inherited implementation has
been corrected against the specified volume-six examples; historical port
snapshots are regression evidence rather than an independent correctness oracle.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.canping_texts import (
    inherited_corpus,
    lookup_record,
    pair_resolution,
    selection_snapshot,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.data import get_nayin

BRANCHES: Tuple[str, ...] = (
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
BRANCH_NUM: Dict[str, int] = {
    branch: index + 1 for index, branch in enumerate(BRANCHES)
}

# 明法（胖胖熊）：月支(月建/八字月支)反向取日宫支。
MONTH_TO_DAY_PALACE: Dict[str, str] = {
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
ELEMENT_ADD: Dict[str, int] = {"水": 27, "火": 27, "土": 50, "木": 0, "金": 0}
# 水1 火2 木3 金4 土5。
ELEMENT_PEI: Dict[str, int] = {"水": 1, "火": 2, "木": 3, "金": 4, "土": 5}

PART_NAMES: Dict[str, str] = {
    "水": "水部",
    "火": "火部",
    "木": "木部",
    "金": "金部",
    "土": "土部",
}

_GANS: Tuple[str, ...] = (
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


@lru_cache(maxsize=1)
def _tiaowen() -> Dict[str, Any]:
    return inherited_corpus()


def nayin_element(year_gz: str) -> str:
    """年干支 → 纳音五行（金/木/水/火/土）。

    Reuses FateBridge's ``get_nayin`` (verified to match horosa's
    ``NAYIN_ELEMENT`` over all 60 ganzhi) and takes its last char.
    """
    cycle = {_GANS[i % 10] + BRANCHES[i % 12] for i in range(60)}
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
    if method == "ming":
        return MONTH_TO_DAY_PALACE[month_branch]
    raise ValueError("method 仅支持 gu（原典日支）或 ming（月支变法）。")


def ming_gong(day_palace_branch: str, hour_branch: str) -> str:
    """命宫：日宫支配卯时起，逆数至生时。"""
    mao = BRANCH_NUM["卯"]
    dp = BRANCH_NUM[day_palace_branch]
    hb = BRANCH_NUM[hour_branch]
    idx = ((dp - (hb - mao) - 1) % 12 + 12) % 12 + 1
    return _branch_from_num(idx)


def compute_number(day_branch: str, hour_branch: str, element: str) -> Dict[str, int]:
    """金锁银匙起数：顺/逆两数。"""
    if element not in ELEMENT_ADD:
        raise ValueError("纳音五行必须是水、火、木、金、土。")
    dp = BRANCH_NUM[day_branch]
    hb = BRANCH_NUM[hour_branch]
    # 卷六金部申日申时例：同支必须走满一周，连首尾十三位。
    shun = ((hb - dp) % 12 or 12) + 1
    ni = ((dp - hb) % 12 or 12) + 1
    zi_round = dp + hb  # 时日皆从子上轮
    add = ELEMENT_ADD.get(element, 0)
    pei = ELEMENT_PEI.get(element, 0)
    base = 2000 + zi_round + add + pei
    return {
        "shun": shun,
        "ni": ni,
        "ziRound": zi_round,
        "numShun": base + shun * 100,
        "numNi": base + ni * 100,
    }


def _lookup(element: str, number: int, kind: str) -> str:
    return str(lookup_record(element, number, kind)["text"])


def _verses(element: str, info: Dict[str, int], kind: Optional[str]) -> Dict[str, Any]:
    def status(text: str) -> str:
        if not text or all(c in "○〇□ \n，。" for c in text):
            return "unavailable_in_local_corpus"
        return (
            "incomplete_transcription"
            if any(c in text for c in "○〇□")
            else "unverified_transcription"
        )

    shun = lookup_record(element, info["numShun"], kind)
    ni = lookup_record(element, info["numNi"], kind)

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
        "numShun": info["numShun"],
        "numNi": info["numNi"],
        "textShun": shun["text"],
        "textNi": ni["text"],
        "statusShun": selected_status(shun),
        "statusNi": selected_status(ni),
        "selectionShun": shun["selection"],
        "selectionNi": ni["selection"],
        "pair_resolution": pair_resolution(shun, ni),
    }


def _kind_for_gender(gender: Optional[str]) -> Optional[str]:
    if gender is None:
        return None
    if not isinstance(gender, str) or normalize_gender(gender) not in {"男", "女"}:
        raise ValueError("参评本命选栏需要明确男／女；未提供时可算数，但不能默认性别。")
    return "female" if normalize_gender(gender) == "女" else "male"


def dayun_sequence(
    day_palace_branch: str,
    hour_branch: str,
    qiyun_age: int = 1,
    count: int = 9,
) -> Tuple[List[Dict[str, Any]], str]:
    """大运序列：命宫顺行 ``count`` 步，每步 10 年。"""
    mg = ming_gong(day_palace_branch, hour_branch)
    start_idx = BRANCH_NUM[mg]
    seq: List[Dict[str, Any]] = []
    for k in range(count):
        branch = _branch_from_num(start_idx + k)
        age_start = qiyun_age + 10 * k
        seq.append(
            {
                "index": k,
                "branch": branch,
                "ageStart": age_start,
                "ageEnd": age_start + 9,
            }
        )
    return seq, mg


def _year_ganzhi(year: int) -> str:
    return _GANS[((year - 4) % 10 + 10) % 10] + BRANCHES[((year - 4) % 12 + 12) % 12]


def calculate(
    *,
    year_gz: str,
    month_branch: str,
    day_branch: str,
    hour_branch: str,
    gender: Optional[str] = None,
    method: str = "gu",
    qiyun_age: int = 1,
    liunian_branch: Optional[str] = None,
    active_dayun_branch: Optional[str] = None,
    include_luck: bool = True,
) -> Dict[str, Any]:
    """本命 + 大运 (+ 可选单点流年) 起数与条文。"""
    kind_main = _kind_for_gender(gender)
    normalized_gender = (
        None if kind_main is None else ("女" if kind_main == "female" else "男")
    )
    element = nayin_element(year_gz)
    dp_branch = day_palace(month_branch, day_branch, method)

    benming = compute_number(dp_branch, hour_branch, element)
    benming_verses = _verses(element, benming, kind_main)

    seq, mg = (
        dayun_sequence(dp_branch, hour_branch, qiyun_age) if include_luck else ([], "")
    )
    dayun: List[Dict[str, Any]] = []
    for step in seq:
        info = compute_number(dp_branch, step["branch"], element)
        dayun.append({**step, **info, "verses": _verses(element, info, "luck")})

    liunian: Optional[Dict[str, Any]] = None
    if liunian_branch:
        if active_dayun_branch not in BRANCHES:
            raise ValueError("单点流年须明确active_dayun_branch，不能默认取第一运。")
        cur_dayun = active_dayun_branch
        info = compute_number(_branch_of(liunian_branch), cur_dayun, element)
        liunian = {
            "taisuiBranch": _branch_of(liunian_branch),
            "dayunBranch": cur_dayun,
            **info,
            "verses": _verses(element, info, "luck"),
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
        "mingGong": mg,
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
    gender: Optional[str] = None,
    method: str = "gu",
    qiyun_age: int = 1,
    birth_year: Optional[int] = None,
    start_age: int = 1,
    end_age: int = 120,
) -> Dict[str, Any]:
    """全表流年：自 ``start_age`` 至 ``end_age`` 虚岁逐岁起数。

    太岁(当年年支)替日宫支、当时大运支替时支起数；每岁按虚岁定位所属大运。
    ``birth_year`` 是出生年柱对应的起始年标签；立春前可能比公历出生年小一。
    未提供出生瞬间的固定四柱调用不能静默接受与年柱矛盾的年标签。
    未知公历年（None，兼容旧0）仍按已知年干支推进相对年序，不猜世纪。
    起运年龄之前没有活动大运，不生成流年编号或诗文；本表不映射UTC区间。
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
    if birth_year is not None and (type(birth_year) is not int or birth_year < 0):
        raise ValueError("公历年标签须为正整数；未知用None或0，不能用布尔值代替。")
    if birth_year and _year_ganzhi(birth_year) != year_gz:
        raise ValueError("流年起始年标签须与出生年柱一致；立春前不能直接用公历出生年。")
    result = calculate(
        year_gz=year_gz,
        month_branch=month_branch,
        day_branch=day_branch,
        hour_branch=hour_branch,
        gender=gender,
        method=method,
        qiyun_age=qiyun_age,
    )
    element = result["element"]
    # 年干支本身足以确定相对太岁。公历纪年未知不能退回出生日支，
    # 也不能从六十年循环任意选择一个公历甲子年。
    cycle = tuple(_GANS[i % 10] + BRANCHES[i % 12] for i in range(60))
    birth_cycle_index = cycle.index(year_gz)
    # 不将九步以后的流年钳制在最后一运；按请求年龄实际展开。
    count = max(9, (end_age - qiyun_age) // 10 + 1)
    sequence, _ = dayun_sequence(
        result["dayPalaceBranch"], hour_branch, qiyun_age, count
    )
    dayun: List[Dict[str, Any]] = []
    for step in sequence:
        info = compute_number(result["dayPalaceBranch"], step["branch"], element)
        dayun.append({**step, **info, "verses": _verses(element, info, "luck")})

    def dayun_at(age: int) -> Optional[Dict[str, Any]]:
        k = (age - qiyun_age) // 10
        if k < 0:
            return None
        return dayun[k]

    rows: List[Dict[str, Any]] = []
    for age in range(start_age, end_age + 1):
        year = birth_year + age - 1 if birth_year else None
        ganzhi = cycle[(birth_cycle_index + age - 1) % 60]
        taisui = ganzhi[1]
        row: Dict[str, Any] = {
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
        "birth_pillar_year": birth_year or None,
        "year_boundary": (
            "provided_year_labels_only"
            if birth_year
            else "relative_ganzhi_year_labels_only"
        ),
        "age_policy": "relative_sexagenary_year_ordinal; no_actual_boundaries",
    }


def build_snapshot_text(result: Dict[str, Any]) -> str:
    """渲染 [起盘]/[本命]/[大运·歲運]/[流年·歲運] 四段中文快照。"""
    if not result:
        return ""
    lines: List[str] = []
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
