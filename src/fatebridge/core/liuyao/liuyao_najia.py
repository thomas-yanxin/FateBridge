"""Mount Najia stems and branches, palace positions, kinship and spirits."""

from typing import Any

from fatebridge.core.liuyao.liuyao_casting import SIX_YAO_NAMES

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


# 纳甲歌的内、外卦纳干，顺序与纳支表一致。
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


BAGONG_BASES = [
    ("乾", "111111", "金"),
    ("坎", "010010", "水"),
    ("艮", "001001", "土"),
    ("震", "100100", "木"),
    ("巽", "011011", "木"),
    ("离", "101101", "火"),
    ("坤", "000000", "土"),
    ("兑", "110110", "金"),
]


BAGONG_POSITION_INFO = [
    ("本宫", "000000", 6),
    ("一世", "100000", 1),
    ("二世", "110000", 2),
    ("三世", "111000", 3),
    ("四世", "111100", 4),
    ("五世", "111110", 5),
    ("游魂", "111010", 4),
    ("归魂", "000010", 3),
]


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


def _xor_binary(code: str, mask: str) -> str:
    return "".join("1" if a != b else "0" for a, b in zip(code, mask))


def _build_hexagram_palace_lookup() -> dict[str, dict[str, Any]]:
    """根据 8 本宫 × 8 卦位 × XOR 掩码生成 64 卦 → 宫 / 世爻 / 宫五行 查表。"""
    lookup: dict[str, dict[str, Any]] = {}
    for palace_name, base_code, palace_element in BAGONG_BASES:
        for position_name, mask, shi_line in BAGONG_POSITION_INFO:
            code = _xor_binary(base_code, mask)
            # 应爻 = (世爻 + 3 - 1) % 6 + 1 (1-indexed)
            ying_line = ((shi_line + 2) % 6) + 1
            lookup[code] = {
                "palace": palace_name,
                "palace_element": palace_element,
                "position": position_name,
                "shi_line": shi_line,
                "ying_line": ying_line,
            }
    return lookup


HEXAGRAM_PALACE_LOOKUP: dict[str, dict[str, Any]] = _build_hexagram_palace_lookup()


def _decode_trigrams(code: str) -> tuple[str, str]:
    """拆分六位二进制到 (下卦, 上卦) 三画卦名。"""
    inv = {
        v: k
        for k, v in {
            "乾": "111",
            "坎": "010",
            "艮": "001",
            "震": "100",
            "巽": "011",
            "离": "101",
            "坤": "000",
            "兑": "110",
        }.items()
    }
    lower = inv.get(code[0:3])
    upper = inv.get(code[3:6])
    return lower or "?", upper or "?"


def _liuqin_against_palace(palace_element: str, line_element: str) -> str:
    if palace_element == line_element:
        return "兄弟"
    generates = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
    controls = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}
    if generates.get(line_element) == palace_element:
        return "父母"  # 生宫者
    if generates.get(palace_element) == line_element:
        return "子孙"  # 宫所生
    if controls.get(line_element) == palace_element:
        return "官鬼"  # 克宫者
    if controls.get(palace_element) == line_element:
        return "妻财"  # 宫所克
    return "平"


def build_sixyao_enrichment(
    current_code: str,
    changed_code: str,
    day_gan: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """生成本卦信息 + 六爻纳甲/世应/六亲/六神。lines 下标 0=初爻，5=上爻。"""

    current_info = HEXAGRAM_PALACE_LOOKUP.get(current_code, {})
    changed_info = HEXAGRAM_PALACE_LOOKUP.get(changed_code, {})

    lower_trigram, upper_trigram = _decode_trigrams(current_code)
    lower_branches = TRIGRAM_LOWER_BRANCHES.get(lower_trigram, ("", "", ""))
    upper_branches = TRIGRAM_UPPER_BRANCHES.get(upper_trigram, ("", "", ""))
    branches = list(lower_branches) + list(upper_branches)

    # 之卦地支 (仅作参考, 用于动爻变后的六亲比对)
    changed_lower_trigram, changed_upper_trigram = _decode_trigrams(changed_code)
    stems = [TRIGRAM_STEMS[lower_trigram][0]] * 3 + [
        TRIGRAM_STEMS[upper_trigram][1]
    ] * 3
    changed_stems = [TRIGRAM_STEMS[changed_lower_trigram][0]] * 3 + [
        TRIGRAM_STEMS[changed_upper_trigram][1]
    ] * 3
    changed_branches = list(
        TRIGRAM_LOWER_BRANCHES.get(changed_lower_trigram, ("", "", ""))
    ) + list(TRIGRAM_UPPER_BRANCHES.get(changed_upper_trigram, ("", "", "")))

    palace_element = current_info.get("palace_element", "")
    shi_line = current_info.get("shi_line", 0)
    ying_line = current_info.get("ying_line", 0)

    offset = LIUSHEN_OFFSET_BY_STEM.get(day_gan or "", 0)

    enriched_lines: list[dict[str, Any]] = []
    for i in range(6):
        branch = branches[i]
        element = BRANCH_TO_ELEMENT.get(branch, "")
        liuqin = _liuqin_against_palace(palace_element, element) if element else "平"
        # 动爻后的变爻地支 + 之卦六亲 (用本宫五行)
        changed_branch = changed_branches[i] if changed_branches[i] else branch
        changed_element = BRANCH_TO_ELEMENT.get(changed_branch, "")
        changed_liuqin = (
            _liuqin_against_palace(palace_element, changed_element)
            if changed_element
            else "平"
        )
        position_label = SIX_YAO_NAMES[i]
        position_num = i + 1
        shi_ying = ""
        if position_num == shi_line:
            shi_ying = "世"
        elif position_num == ying_line:
            shi_ying = "应"
        liushen = LIUSHEN_CYCLE[(offset + i) % 6]
        enriched_lines.append(
            {
                "stem": stems[i],
                "branch": branch,
                "element": element,
                "liuqin": liuqin,
                "shi_ying": shi_ying,
                "liushen": liushen,
                "position_label": position_label,
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
