"""Mount Najia stems/branches, palace/shi-ying, kinship, spirits, Gua Shen, and Shen Sha."""

from __future__ import annotations

from typing import Any

from fatebridge.core.hexagram_relations import (
    BAGONG_BASES,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    HEXAGRAM_PALACE_LOOKUP,
)
from fatebridge.core.liuyao.casting import SIX_YAO_NAMES

TRIGRAM_LOWER_BRANCHES = {
    "乾": ("子", "寅", "辰"),
    "坎": ("寅", "辰", "午"),
    "艮": ("辰", "午", "申"),
    "震": ("子", "寅", "辰"),
    "巽": ("丑", "亥", "酉"),
    "离": ("卯", "丑", "亥"),
    "坤": ("未", "巳", "卯"),
    "兑": ("巳", "卯", "丑"),
}

TRIGRAM_UPPER_BRANCHES = {
    "乾": ("午", "申", "戌"),
    "坎": ("申", "戌", "子"),
    "艮": ("戌", "子", "寅"),
    "震": ("午", "申", "戌"),
    "巽": ("未", "巳", "卯"),
    "离": ("酉", "未", "巳"),
    "坤": ("丑", "亥", "酉"),
    "兑": ("亥", "酉", "未"),
}

TRIGRAM_STEMS = {
    "乾": ("甲", "壬"),
    "坎": ("戊", "戊"),
    "艮": ("丙", "丙"),
    "震": ("庚", "庚"),
    "巽": ("辛", "辛"),
    "离": ("己", "己"),
    "坤": ("乙", "癸"),
    "兑": ("丁", "丁"),
}

BRANCH_TO_ELEMENT = {
    "寅": "木",
    "卯": "木",
    "巳": "火",
    "午": "火",
    "申": "金",
    "酉": "金",
    "亥": "水",
    "子": "水",
    "辰": "土",
    "戌": "土",
    "丑": "土",
    "未": "土",
}

LIUSHEN_CYCLE = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")
LIUSHEN_OFFSET_BY_STEM = {
    "甲": 0,
    "乙": 0,
    "丙": 1,
    "丁": 1,
    "戊": 2,
    "己": 3,
    "庚": 4,
    "辛": 4,
    "壬": 5,
    "癸": 5,
}

_CODE_TO_TRIGRAM = {
    "111": "乾",
    "010": "坎",
    "001": "艮",
    "100": "震",
    "011": "巽",
    "101": "离",
    "000": "坤",
    "110": "兑",
}

_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

TIANYI_GUIREN = {
    "甲": ("丑", "未"),
    "戊": ("丑", "未"),
    "庚": ("丑", "未"),
    "乙": ("子", "申"),
    "己": ("子", "申"),
    "丙": ("亥", "酉"),
    "丁": ("亥", "酉"),
    "壬": ("卯", "巳"),
    "癸": ("卯", "巳"),
    "辛": ("午", "寅"),
}
LUSHEN_BY_STEM = {
    "甲": "寅",
    "乙": "卯",
    "丙": "巳",
    "丁": "午",
    "戊": "巳",
    "己": "午",
    "庚": "申",
    "辛": "酉",
    "壬": "亥",
    "癸": "子",
}
YANGREN_BY_STEM = {
    "甲": "卯",
    "乙": "辰",
    "丙": "午",
    "丁": "未",
    "戊": "午",
    "己": "未",
    "庚": "酉",
    "辛": "戌",
    "壬": "子",
    "癸": "丑",
}

_TRIAD_SHENSHA_SPECS: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "驿马",
        {
            "申": "寅",
            "子": "寅",
            "辰": "寅",
            "寅": "申",
            "午": "申",
            "戌": "申",
            "亥": "巳",
            "卯": "巳",
            "未": "巳",
            "巳": "亥",
            "酉": "亥",
            "丑": "亥",
        },
    ),
    (
        "桃花",
        {
            "申": "酉",
            "子": "酉",
            "辰": "酉",
            "寅": "卯",
            "午": "卯",
            "戌": "卯",
            "亥": "子",
            "卯": "子",
            "未": "子",
            "巳": "午",
            "酉": "午",
            "丑": "午",
        },
    ),
    (
        "将星",
        {
            "申": "子",
            "子": "子",
            "辰": "子",
            "寅": "午",
            "午": "午",
            "戌": "午",
            "亥": "卯",
            "卯": "卯",
            "未": "卯",
            "巳": "酉",
            "酉": "酉",
            "丑": "酉",
        },
    ),
    (
        "劫煞",
        {
            "申": "巳",
            "子": "巳",
            "辰": "巳",
            "寅": "亥",
            "午": "亥",
            "戌": "亥",
            "亥": "申",
            "卯": "申",
            "未": "申",
            "巳": "寅",
            "酉": "寅",
            "丑": "寅",
        },
    ),
    (
        "谋星",
        {
            "申": "戌",
            "子": "戌",
            "辰": "戌",
            "寅": "辰",
            "午": "辰",
            "戌": "辰",
            "亥": "丑",
            "卯": "丑",
            "未": "丑",
            "巳": "未",
            "酉": "未",
            "丑": "未",
        },
    ),
    (
        "华盖",
        {
            "申": "辰",
            "子": "辰",
            "辰": "辰",
            "寅": "戌",
            "午": "戌",
            "戌": "戌",
            "亥": "未",
            "卯": "未",
            "未": "未",
            "巳": "丑",
            "酉": "丑",
            "丑": "丑",
        },
    ),
)


def _decode_trigrams(code: str) -> tuple[str, str]:
    return _CODE_TO_TRIGRAM.get(code[0:3], "?"), _CODE_TO_TRIGRAM.get(code[3:6], "?")


def liuqin_against_palace(palace_element: str, line_element: str) -> str:
    """Resolve 六亲 of line_element relative to the hexagram palace element."""
    if not palace_element or not line_element:
        return "平"
    if palace_element == line_element:
        return "兄弟"
    if ELEMENT_GENERATES.get(line_element) == palace_element:
        return "父母"
    if ELEMENT_GENERATES.get(palace_element) == line_element:
        return "子孙"
    if ELEMENT_CONTROLS.get(line_element) == palace_element:
        return "官鬼"
    if ELEMENT_CONTROLS.get(palace_element) == line_element:
        return "妻财"
    return "平"


def build_sixyao_enrichment(
    current_code: str,
    changed_code: str,
    day_gan: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build hexagram palace info and 6 bottom-to-top Najia/Liuqin/Liushen rows."""
    current_info: dict[str, Any] = dict(HEXAGRAM_PALACE_LOOKUP.get(current_code, {}))
    changed_info: dict[str, Any] = dict(HEXAGRAM_PALACE_LOOKUP.get(changed_code, {}))

    lower_trigram, upper_trigram = _decode_trigrams(current_code)
    branches = list(TRIGRAM_LOWER_BRANCHES.get(lower_trigram, ("", "", ""))) + list(
        TRIGRAM_UPPER_BRANCHES.get(upper_trigram, ("", "", ""))
    )
    stems = [TRIGRAM_STEMS[lower_trigram][0]] * 3 + [
        TRIGRAM_STEMS[upper_trigram][1]
    ] * 3

    changed_lower, changed_upper = _decode_trigrams(changed_code)
    changed_stems = [TRIGRAM_STEMS[changed_lower][0]] * 3 + [
        TRIGRAM_STEMS[changed_upper][1]
    ] * 3
    changed_branches = list(
        TRIGRAM_LOWER_BRANCHES.get(changed_lower, ("", "", ""))
    ) + list(TRIGRAM_UPPER_BRANCHES.get(changed_upper, ("", "", "")))

    palace_element = str(current_info.get("palace_element", ""))
    shi_line = int(current_info.get("shi_line", 0))
    ying_line = int(current_info.get("ying_line", 0))
    offset = LIUSHEN_OFFSET_BY_STEM.get(day_gan or "", 0)

    enriched_lines: list[dict[str, Any]] = []
    for i in range(6):
        branch = branches[i]
        element = BRANCH_TO_ELEMENT.get(branch, "")
        liuqin = liuqin_against_palace(palace_element, element)
        changed_branch = changed_branches[i] or branch
        changed_element = BRANCH_TO_ELEMENT.get(changed_branch, "")
        changed_liuqin = liuqin_against_palace(palace_element, changed_element)
        position_num = i + 1
        shi_ying = (
            "世"
            if position_num == shi_line
            else ("应" if position_num == ying_line else "")
        )
        enriched_lines.append(
            {
                "stem": stems[i],
                "branch": branch,
                "element": element,
                "liuqin": liuqin,
                "shi_ying": shi_ying,
                "liushen": LIUSHEN_CYCLE[(offset + i) % 6],
                "position_label": SIX_YAO_NAMES[i],
                "position": position_num,
                "changed_stem": changed_stems[i],
                "changed_branch": changed_branch if changed_branch != branch else None,
                "changed_liuqin": changed_liuqin if changed_branch != branch else None,
            }
        )

    hexagram_info = {
        "current_palace": current_info.get("palace"),
        "current_position": current_info.get("position"),
        "current_palace_element": palace_element,
        "shi_line": shi_line,
        "ying_line": ying_line,
        "changed_palace": changed_info.get("palace"),
        "changed_position": changed_info.get("position"),
        "changed_palace_element": changed_info.get("palace_element"),
    }
    return hexagram_info, enriched_lines


def compute_gua_shen(
    *,
    lines: list[dict[str, Any]],
    shi_line: int,
    palace_element: str,
) -> dict[str, Any]:
    """Compute 卦身 (阳世子起、阴世午起, counting up to 世爻)."""
    shi_value = int(lines[shi_line - 1]["value"])
    start_index = 0 if shi_value == 1 else 6
    branch = _BRANCHES[(start_index + shi_line - 1) % 12]
    element = BRANCH_TO_ELEMENT[branch]
    return {
        "branch": branch,
        "element": element,
        "liuqin": liuqin_against_palace(palace_element, element),
        "shi_line": shi_line,
        "shi_yin_yang": "阳" if shi_value == 1 else "阴",
        "present_positions": [
            line["position"] for line in lines if line["branch"] == branch
        ],
    }


def compute_hidden_spirits(
    *,
    normalized_lines: list[dict[str, Any]],
    current_palace: str,
    day_gan: str | None,
) -> list[dict[str, Any]]:
    """Compute 伏神 strictly from 六亲 missing in 本卦 (never suppressed by 变爻)."""
    palace_base = next(
        code for palace, code, _ in BAGONG_BASES if palace == current_palace
    )
    _, palace_lines = build_sixyao_enrichment(palace_base, palace_base, day_gan)
    present_kin = {line["liuqin"] for line in normalized_lines}
    changed_kin_positions: dict[str, list[int]] = {}
    for line in normalized_lines:
        if line.get("change") and line.get("changed_liuqin"):
            changed_kin_positions.setdefault(line["changed_liuqin"], []).append(
                line["position"]
            )
    hidden: list[dict[str, Any]] = []
    for i, row in enumerate(palace_lines):
        if row["liuqin"] in present_kin:
            continue
        changed_positions = changed_kin_positions.get(row["liuqin"], [])
        hidden.append(
            {
                "position": row["position"],
                "branch": row["branch"],
                "element": row["element"],
                "liuqin": row["liuqin"],
                "flying_branch": normalized_lines[i]["branch"],
                "flying_liuqin": normalized_lines[i]["liuqin"],
                "present_in_changed": bool(changed_positions),
                "changed_positions": changed_positions,
            }
        )
    return hidden


def compute_shensha(
    *,
    day_gan: str,
    day_branch: str,
    lines: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[int, list[str]]]:
    """Compute 六爻神煞表 (天乙贵人/驿马/桃花/禄神/羊刃/将星/劫煞/谋星/华盖)."""
    star_branches: dict[str, tuple[str, ...]] = {
        "天乙贵人": TIANYI_GUIREN.get(day_gan, ()),
        "禄神": (LUSHEN_BY_STEM[day_gan],) if day_gan in LUSHEN_BY_STEM else (),
        "羊刃": (YANGREN_BY_STEM[day_gan],) if day_gan in YANGREN_BY_STEM else (),
    }
    for name, table in _TRIAD_SHENSHA_SPECS:
        target = table.get(day_branch)
        star_branches[name] = (target,) if target else ()

    ordered_names = (
        "天乙贵人",
        "驿马",
        "桃花",
        "禄神",
        "羊刃",
        "将星",
        "劫煞",
        "谋星",
        "华盖",
    )
    table_out: dict[str, dict[str, Any]] = {}
    per_line: dict[int, list[str]] = {line["position"]: [] for line in lines}
    for name in ordered_names:
        branches = list(star_branches.get(name, ()))
        positions = [line["position"] for line in lines if line["branch"] in branches]
        for pos in positions:
            per_line[pos].append(name)
        table_out[name] = {"branches": branches, "positions": positions}
    return table_out, per_line
