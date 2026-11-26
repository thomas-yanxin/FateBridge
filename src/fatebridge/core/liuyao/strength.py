"""Liuyao branch strength, day-clash (暗动/日破), stages, progressions, patterns & fanfu."""

from __future__ import annotations

from typing import Any

from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES
from fatebridge.utils.data import BRANCH_CONFLICTS

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = dict(zip(BRANCHES, "水土木木土火火土金金土水"))
GENERATES = ELEMENT_GENERATES
CONTROLS = ELEMENT_CONTROLS
COMBINES = dict(zip("子丑寅亥卯戌辰酉巳申午未", "丑子亥寅戌卯酉辰申巳未午"))

# 《增删卜易》进神七组 (另注：多爻变时 戌->丑 若跨宫可另参考)
ADVANCES = {
    "亥": "子",
    "寅": "卯",
    "巳": "午",
    "申": "酉",
    "丑": "辰",
    "辰": "未",
    "未": "戌",
}
RETREATS = {v: k for k, v in ADVANCES.items()}

THREE_HARMONY_GROUPS: tuple[tuple[str, str], ...] = (
    ("申子辰", "水"),
    ("巳酉丑", "金"),
    ("寅午戌", "火"),
    ("亥卯未", "木"),
)

# 增删卜易 四长生/帝旺/墓/绝表（火生在寅顺数，午帝旺、戌墓、亥绝）
STAGES: dict[str, dict[str, str]] = {
    "金": {"巳": "长生", "酉": "帝旺", "丑": "墓", "寅": "绝"},
    "木": {"亥": "长生", "卯": "帝旺", "未": "墓", "申": "绝"},
    "水": {"申": "长生", "子": "帝旺", "辰": "墓", "巳": "绝"},
    "土": {"申": "长生", "子": "帝旺", "辰": "墓", "巳": "绝"},
    "火": {"寅": "长生", "午": "帝旺", "戌": "墓", "亥": "绝"},
}

ZENGSHAN_PDF_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/4/42/"
    "NLC416-12jh005345-45344_%E5%A2%9E%E5%88%AA%E5%8D%9C%E6%98%93.pdf"
)
SOURCES = {
    "najia": f"{ZENGSHAN_PDF_URL}#page=20",
    "relations": f"{ZENGSHAN_PDF_URL}#page=60",
    "fanfu": f"{ZENGSHAN_PDF_URL}#page=88",
    "stages": f"{ZENGSHAN_PDF_URL}#page=97",
    "hidden": f"{ZENGSHAN_PDF_URL}#page=110",
    "progression": f"{ZENGSHAN_PDF_URL}#page=123",
}

LIUCHONG_HEXAGRAM_CODES = frozenset(
    {
        "111111",
        "000000",
        "100100",
        "011011",
        "010010",
        "101101",
        "001001",
        "110110",
        "100111",
        "111100",
    }
)
LIUHE_HEXAGRAM_CODES = frozenset(
    {
        "111000",
        "000111",
        "000100",
        "100000",
        "010110",
        "110010",
        "001101",
        "101001",
    }
)
EXPLICIT_FANFU_EXAMPLES = {("111111", "000000"): ("反吟", 88)}


def clash(branch: str) -> str:
    """Return the opposing branch (六冲)."""
    return BRANCHES[(BRANCHES.index(branch) + 6) % 12]


def xunkong(day_ganzhi: str) -> list[str]:
    """Compute the two 旬空 branches of a 60-Jiazi day pillar."""
    if (
        len(day_ganzhi) != 2
        or day_ganzhi[0] not in STEMS
        or day_ganzhi[1] not in BRANCHES
    ):
        raise ValueError("旬空需要有效的日干支")
    stem_index = STEMS.index(day_ganzhi[0])
    branch_index = BRANCHES.index(day_ganzhi[1])
    if (stem_index - branch_index) % 2:
        raise ValueError("日干支不在六十甲子中")
    start = (branch_index - stem_index + 10) % 12
    return [BRANCHES[start], BRANCHES[(start + 1) % 12]]


def element_relation(actor: str, target: str) -> str:
    """Return actor -> target five-element relationship."""
    if actor == target:
        return "比和"
    if GENERATES[actor] == target:
        return "生爻"
    if CONTROLS[actor] == target:
        return "克爻"
    if GENERATES[target] == actor:
        return "爻生"
    return "爻克"


def month_strength(branch: str, month: str) -> dict[str, Any]:
    """Classify seasonal month strength of branch under month branch."""
    element, seasonal = ELEMENTS[branch], ELEMENTS[month]
    if branch == month:
        category = "临月建"
    elif clash(month) == branch:
        category = "月破"
    elif element == seasonal:
        category = "同气次旺"
    elif GENERATES[seasonal] == element:
        category = "相"
    else:
        category = "休囚"
    return {
        "category": category,
        "monthly_supported": category in ("临月建", "同气次旺", "相"),
        "residual_qi": element == {"辰": "木", "未": "火", "丑": "水"}.get(month),
    }


def day_value_exception(branch: str, month: str, day: str) -> bool:
    """True when line branch equals day branch (日建临爻，不作月破)."""
    return branch == day


def month_opposition_applies(branch: str, month: str, day: str) -> bool:
    """True when month-clash (月破) is not relieved by sitting on the day branch."""
    return clash(month) == branch and not day_value_exception(branch, month, day)


def branch_facts(branch: str, month: str, day: str, void: list[str]) -> dict[str, Any]:
    """Compute core calendar-branch relation flags for a single line/hidden branch."""
    return {
        "is_xunkong": branch in void,
        "is_month_clash": clash(month) == branch,
        "is_day_clash": clash(day) == branch,
        "is_month_combination": COMBINES[month] == branch,
        "is_day_combination": COMBINES[day] == branch,
        "is_month_branch": branch == month,
        "is_day_branch": branch == day,
        "month_element_relation": element_relation(ELEMENTS[month], ELEMENTS[branch]),
        "day_element_relation": element_relation(ELEMENTS[day], ELEMENTS[branch]),
    }


def classify_day_clash(
    *,
    branch: str,
    is_moving: bool,
    month: str,
    day: str,
    facts: dict[str, Any],
    monthly: dict[str, Any],
    has_moving_support: bool = False,
) -> dict[str, Any]:
    """Classify 日冲 explicitly into dark_moving (暗动), day_broken (日破), or moving_line_clashed."""
    is_month_broken = month_opposition_applies(branch, month, day)
    is_void_clashed = bool(facts["is_xunkong"] and facts["is_day_clash"])
    if not facts["is_day_clash"]:
        return {
            "is_month_broken": is_month_broken,
            "is_void_clashed": False,
            "is_dark_moving": False,
            "is_day_broken": False,
            "day_clash_status": "none",
        }
    if is_moving:
        return {
            "is_month_broken": is_month_broken,
            "is_void_clashed": is_void_clashed,
            "is_dark_moving": False,
            "is_day_broken": False,
            "day_clash_status": "moving_line_clashed",
        }
    day_stage = STAGES[ELEMENTS[branch]].get(day)
    has_support = (
        monthly["monthly_supported"]
        or facts["is_month_combination"]
        or facts["is_day_combination"]
        or facts["is_day_branch"]
        or facts["day_element_relation"] in ("生爻", "比和")
        or day_stage in ("长生", "帝旺")
        or has_moving_support
    )
    if has_support and not is_month_broken:
        return {
            "is_month_broken": False,
            "is_void_clashed": is_void_clashed,
            "is_dark_moving": True,
            "is_day_broken": False,
            "day_clash_status": "dark_moving",
        }
    return {
        "is_month_broken": is_month_broken,
        "is_void_clashed": is_void_clashed,
        "is_dark_moving": False,
        "is_day_broken": True,
        "day_clash_status": "day_broken",
    }


def detect_three_harmony(
    *,
    lines: list[dict[str, Any]],
    dark_moving_positions: set[int],
    month: str,
    day: str,
) -> list[dict[str, Any]]:
    """Detect active 三合局 across moving/dark-moving/changed lines and month/day branches."""
    active_actors: list[dict[str, Any]] = []
    for line in lines:
        pos = line["position"]
        if line["change"] or pos in dark_moving_positions:
            active_actors.append(
                {
                    "location": "visible",
                    "position": pos,
                    "branch": line["branch"],
                    "activity": "动爻" if line["change"] else "暗动",
                }
            )
            if line["change"] and line.get("changed_branch"):
                active_actors.append(
                    {
                        "location": "changed",
                        "position": pos,
                        "branch": line["changed_branch"],
                        "activity": "变爻",
                    }
                )
    calendar_branches = {"month": month, "day": day}
    formations: list[dict[str, Any]] = []
    for triad, element in THREE_HARMONY_GROUPS:
        matched_lines = [a for a in active_actors if a["branch"] in triad]
        matched_line_branches = {a["branch"] for a in matched_lines}
        if not matched_lines:
            continue
        missing = [b for b in triad if b not in matched_line_branches]
        cal_hits = [
            {"role": role, "branch": b}
            for role, b in calendar_branches.items()
            if b in missing
        ]
        if not missing:
            status = "complete_in_lines"
        elif len(missing) == 1 and cal_hits:
            status = "complete_with_calendar"
        elif len(matched_line_branches) == 2:
            status = "pending_one_branch"
        else:
            continue
        formations.append(
            {
                "triad": triad,
                "element": element,
                "status": status,
                "line_members": matched_lines,
                "calendar_members": cal_hits,
                "missing_branches": [
                    b for b in missing if b not in {c["branch"] for c in cal_hits}
                ],
            }
        )
    return formations


def branch_relation(original: str, changed: str) -> str:
    """Return 伏吟 / 反吟 / 其他纳支关系 between original and changed branches."""
    if original == changed:
        return "伏吟"
    if BRANCH_CONFLICTS.get(original) == changed:
        return "反吟"
    return "其他纳支关系"


def build_fanfu_evidence(
    *,
    current_code: str,
    changed_code: str,
    base_branches: list[str],
    changed_chart_branches: list[str],
) -> dict[str, Any]:
    """Build compact 反吟/伏吟 structural evidence for moving lines and trigrams."""
    moving = [i + 1 for i in range(6) if current_code[i] != changed_code[i]]
    relations = [
        {
            "position": p,
            "original_branch": base_branches[p - 1],
            "changed_branch": changed_chart_branches[p - 1],
            "nazhi_relation": branch_relation(
                base_branches[p - 1], changed_chart_branches[p - 1]
            ),
        }
        for p in moving
    ]
    regions = []
    for name, start in (("inner", 0), ("outer", 3)):
        original = current_code[start : start + 3]
        changed = changed_code[start : start + 3]
        old = base_branches[start : start + 3]
        new = changed_chart_branches[start : start + 3]
        comparisons = [branch_relation(a, b) for a, b in zip(old, new)]
        nazhi = (
            "未动"
            if original == changed
            else comparisons[0] if len(set(comparisons)) == 1 else "其他纳支关系"
        )
        regions.append(
            {
                "region": name,
                "base_trigram_code": original,
                "changed_trigram_code": changed,
                "trigram_changed": original != changed,
                "base_branches": old,
                "changed_chart_branches": new,
                "nazhi_relation": nazhi,
                "moving_positions": [p for p in moving if start < p <= start + 3],
            }
        )
    example = EXPLICIT_FANFU_EXAMPLES.get((current_code, changed_code))
    explicit = (
        {
            "base_code": current_code,
            "changed_code": changed_code,
            "kind": example[0],
            "pdf_page": example[1],
            "source_url": f"{ZENGSHAN_PDF_URL}#page={example[1]}",
        }
        if example
        else None
    )
    return {
        "ruleset_id": "zengshan_fanfu_v6",
        "source_url": SOURCES["fanfu"],
        "regions": regions,
        "moving_line_relations": relations,
        "explicit_body_example": explicit,
    }


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
    if current_code in LIUCHONG_HEXAGRAM_CODES:
        patterns.append({"name": "本卦六冲", "basis": "八纯卦及无妄、大壮"})
    if current_code in LIUHE_HEXAGRAM_CODES:
        patterns.append({"name": "本卦六合", "basis": "天地否泰等八六合卦"})
    if current_code != changed_code:
        if changed_code in LIUCHONG_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六冲", "basis": "之卦转为六冲"})
        if changed_code in LIUHE_HEXAGRAM_CODES:
            patterns.append({"name": "变卦六合", "basis": "之卦归六合"})

    fu_count = 0
    fan_count = 0
    for idx in moving_indices:
        if not 0 <= idx < 6:
            continue
        orig_branch, new_branch = current_branches[idx], changed_branches[idx]
        if not orig_branch or not new_branch:
            continue
        if orig_branch == new_branch:
            fu_count += 1
        elif BRANCH_CONFLICTS.get(orig_branch) == new_branch:
            fan_count += 1
    if fu_count and fu_count == len(moving_indices):
        patterns.append({"name": "伏吟", "basis": "实际动爻之支均与原支相同"})
    elif fu_count:
        patterns.append(
            {"name": "局部伏吟", "basis": f"{fu_count}个动爻之支与原支相同"}
        )
    if fan_count and fan_count == len(moving_indices):
        patterns.append({"name": "反吟", "basis": "实际动爻之支均与原支相冲"})
    elif fan_count:
        patterns.append(
            {"name": "局部反吟", "basis": f"{fan_count}个动爻之支与原支相冲"}
        )

    if fanfu:
        if fanfu.get("explicit_body_example"):
            patterns.append(
                {
                    "name": "卦体" + fanfu["explicit_body_example"]["kind"],
                    "basis": "底本明列卦体例",
                }
            )
        for region in fanfu["regions"]:
            if region["nazhi_relation"] in ("反吟", "伏吟"):
                label = "内卦" if region["region"] == "inner" else "外卦"
                patterns.append(
                    {
                        "name": label + "纳支" + region["nazhi_relation"],
                        "basis": f"{label}变后三爻纳支全{region['nazhi_relation']}",
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


def build_moving_focus_guidance(
    lines: list[dict[str, Any]],
    *,
    shi_line: int,
) -> dict[str, Any]:
    """Structured multi-moving and static hexagram focus guidance (《增删卜易》)."""
    moving_positions = [line["position"] for line in lines if line.get("change")]
    static_positions = [line["position"] for line in lines if not line.get("change")]
    count = len(moving_positions)
    if count == 0:
        mode = "static"
        primary = [shi_line] if shi_line else []
        rule = "静卦无动爻，以用神旺衰及世应生克为主；旺相暗动之静爻亦可为枢机"
    elif count == 1:
        mode = "single_moving"
        primary = list(moving_positions)
        rule = "一爻独动，专察动爻及变爻回头生克、进退神与用神关系"
    elif count == 2:
        mode = "two_moving"
        yin_moving = [p for p in moving_positions if lines[p - 1]["value"] == 0]
        primary = yin_moving or list(moving_positions)
        rule = "两爻动兼看两动爻间生克合冲与对用神之向背；传统亦多参阴爻为主"
    elif count == 3:
        mode = "three_moving"
        primary = [moving_positions[1]]
        rule = "三爻动动爻繁杂，重察中间动爻、用神及三合局趋向"
    elif count == 4:
        mode = "four_moving"
        primary = list(static_positions)
        rule = "四爻动主事体多变，宜兼取二静爻（尤其临世或用神者）与动爻合局参照"
    elif count == 5:
        mode = "five_moving"
        primary = list(static_positions)
        rule = "五爻动以独静一爻为核心枢机，并参用神及变卦大势"
    else:
        mode = "all_moving"
        primary = [shi_line] if shi_line else []
        rule = "六爻全动以变卦体势、用神及世爻旺衰为重；乾坤两纯卦另参用九用六"
    return {
        "moving_count": count,
        "moving_positions": moving_positions,
        "static_positions": static_positions,
        "mode": mode,
        "primary_focus_positions": primary,
        "rule": rule,
    }
