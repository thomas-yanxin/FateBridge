"""Consolidated Taiyi core calculation: geometry, 72-ju core, patterns, gates, cycles & ten essences."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.metaphysics.common import chinese_numeral

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
RING = "子丑艮寅卯辰巽巳午未坤申酉戌乾亥"
DISPLAY_ORDER = "巽巳午未坤申酉戌乾亥子丑艮寅卯辰"

PALACES = {
    1: "乾",
    2: "午",
    3: "艮",
    4: "卯",
    5: "中",
    6: "酉",
    7: "坤",
    8: "子",
    9: "巽",
}
PALACE_ORDER = (1, 8, 3, 4, 9, 2, 7, 6)

DOORS = tuple("开休生伤杜景死惊")
GOOD_DOORS = frozenset({"开", "休", "生"})
GOOD = GOOD_DOORS

SECTORS = {
    spirit: number
    for number, spirits in (
        (1, "戌乾亥"),
        (8, "子"),
        (3, "丑艮寅"),
        (4, "卯"),
        (9, "辰巽巳"),
        (2, "午"),
        (7, "未坤申"),
        (6, "酉"),
    )
    for spirit in spirits
}

TaiyiShijiProfile = Literal[
    "jinjing_vol2_rotation_v1",
    "jinjing_vol3_table_v1",
    "jinjing_vol3_table_literal_v1",
]
DEFAULT_SHIJI_PROFILE = "jinjing_vol2_rotation_v1"
SHIJI_PROFILES = (
    "jinjing_vol2_rotation_v1",
    "jinjing_vol3_table_v1",
    "jinjing_vol3_table_literal_v1",
)

TaiyiTablePolicy = Literal["computed", "printed_table"]
DEFAULT_TABLE_POLICY: TaiyiTablePolicy = "computed"
TAIYI_TABLE_POLICIES = ("computed", "printed_table")

# Complete Siku Quanshu《太乙金镜式经》Vol. 3 printed table overrides where the
# woodblock table diverges from pure Vol. 2 counting/rotation arithmetic.
VOL3_PRINTED_TABLE_OVERRIDES: dict[tuple[bool, int], dict[str, Any]] = {
    (False, 39): {"main_count": 25},
    (False, 50): {"main_count": 6},
    (True, 11): {"guest_count": 36},
    (True, 15): {"guest_count": 29},
    (True, 25): {"main_count": 21},
    (True, 26): {"main_count": 31},
    (True, 27): {"main_count": 39},
    (True, 37): {"shiji": "午", "guest_count": 25},
    (True, 43): {"shiji": "坤", "guest_count": 38},
    (True, 44): {"shiji": "酉", "guest_count": 31},
    (True, 46): {"guest_count": 2},
    (True, 70): {"main_count": 22},
}

YIN_37_43_44_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "ju": 37,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 25,
        "source": "《太乙金镜式经》卷二通则（同1599年米泽本《武经总要》）",
    },
    {
        "ju": 37,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "午",
        "shiji_literal": "大威",
        "guest_count": 27,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第37局始击「大威」（午），客算依卷二重算27",
    },
    {
        "ju": 37,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "午",
        "shiji_literal": "大威",
        "guest_count": 25,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第37局原表字面「大威」（午）及客算25",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "巳",
        "shiji_literal": "大神",
        "guest_count": 1,
        "source": "《太乙金镜式经》卷二通则（同1599年米泽本《武经总要》）",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第43局「大武」（坤）及客算38",
    },
    {
        "ju": 43,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第43局「大武」（坤）及客算38",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol2_rotation_v1",
        "shiji": "坤",
        "shiji_literal": "大武",
        "guest_count": 38,
        "source": "《太乙金镜式经》卷二通则（同1599年米泽本《武经总要》）",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol3_table_v1",
        "shiji": "酉",
        "shiji_literal": "太蔟",
        "guest_count": 31,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第44局「太蔟」（酉）及客算31",
    },
    {
        "ju": 44,
        "profile": "jinjing_vol3_table_literal_v1",
        "shiji": "酉",
        "shiji_literal": "太蔟",
        "guest_count": 31,
        "source": "《太乙金镜式经》（四库全书本）卷三阴遁第44局「太蔟」（酉）及客算31",
    },
)
SHIJI_EDITION_WITNESSES = {
    (row["ju"], row["profile"]): row for row in YIN_37_43_44_VARIANTS
}


class CountStep(TypedDict):
    palace: str
    value: int
    kind: Literal["间神起算", "正宫", "本宫数"]


class CountTrace(TypedDict):
    count: int
    path: list[CountStep]
    terminal_palace: str
    terminal_excluded: bool
    counting_rule: str


def count_to_taiyi(marker: str, taiyi_number: int) -> CountTrace:
    """Count the starting intercalary spirit once, then principal palaces before Taiyi."""
    if (
        type(marker) is not str
        or marker not in set(RING)
        or type(taiyi_number) is not int
        or taiyi_number not in PALACE_ORDER
    ):
        raise ValueError("太乙计数需要十六神及非中五的太乙宫数")
    principal = {label: number for number, label in PALACES.items() if number != 5}
    path: list[CountStep] = []
    if marker not in principal:
        path.append({"palace": marker, "value": 1, "kind": "间神起算"})
        start = (RING.index(marker) + 1) % 16
    else:
        start = RING.index(marker)
    index = start
    while RING[index] != PALACES[taiyi_number]:
        position = RING[index]
        if position in principal:
            path.append(
                {"palace": position, "value": principal[position], "kind": "正宫"}
            )
        index = (index + 1) % 16
    same_principal = not path
    if same_principal:
        path.append({"palace": marker, "value": taiyi_number, "kind": "本宫数"})
    return {
        "count": sum(step["value"] for step in path),
        "path": path,
        "terminal_palace": PALACES[taiyi_number],
        "terminal_excluded": not same_principal,
        "counting_rule": "同宫取本宫数" if same_principal else "数至太乙宫前",
    }


def general_for_count(count: int) -> int:
    """Return the palace number (including center 5) from a general count 1..40."""
    if not 1 <= count <= 40:
        raise ValueError("太乙主客算必须在1至40之间")
    return count % 10 or count // 10


def count_labels(count: int) -> list[str]:
    """Return classical three-realms & Du-Sai count labels for 1..40."""
    if type(count) is not int or not 1 <= count <= 40:
        raise ValueError("主客算分类需要1至40的整数")
    labels: list[str] = []
    if count < 10:
        labels.append("无天")
    if 1 <= count % 10 <= 4:
        labels.append("无地")
    if count % 10 == 0:
        labels.append("无人")
    ten, five, one = count // 10 * 10, count % 10 // 5 * 5, count % 5
    if ten and five and one:
        labels.append("三才足数（数理推导）")
    if count % 10 == 5:
        labels.append("杜塞（淘金歌）")
    return labels


def rotate_shiji(wenchang: object, jishen: object) -> dict[str, Any]:
    """Place 計神 on 和德(艮) and advance along the 16-spirit ring to 文昌."""
    if (
        type(wenchang) is not str
        or len(wenchang) != 1
        or wenchang not in RING
        or type(jishen) is not str
        or len(jishen) != 1
        or jishen not in BRANCHES
    ):
        raise ValueError("始击推步须给定单一文昌十六神及计神十二支")
    heaven_start = RING.index(jishen)
    earth_start = RING.index("艮")
    intervals = (RING.index(wenchang) - heaven_start) % len(RING)
    pairs = [
        {
            "step": step,
            "heaven_spirit": RING[(heaven_start + step) % len(RING)],
            "earth_spirit": RING[(earth_start + step) % len(RING)],
        }
        for step in range(intervals + 1)
    ]
    return {
        "wenchang": wenchang,
        "jishen": jishen,
        "earth_anchor": "艮",
        "direction": "顺行十六神",
        "step_count": intervals,
        "pairs": pairs,
        "derived_shiji": pairs[-1]["earth_spirit"],
    }


def resolve_shiji_variant(
    *,
    yin: bool,
    ju: int,
    wenchang: str,
    jishen: str,
    shiji_profile: str | None = None,
) -> dict[str, Any]:
    profile = DEFAULT_SHIJI_PROFILE if shiji_profile is None else shiji_profile
    if profile not in SHIJI_PROFILES:
        raise ValueError(f"shiji_profile须明确选择{'、'.join(SHIJI_PROFILES)}")
    witness = (
        SHIJI_EDITION_WITNESSES.get((ju, profile))
        if yin and profile != DEFAULT_SHIJI_PROFILE
        else None
    )
    rotation = rotate_shiji(wenchang, jishen)
    return {
        "profile": profile if witness else DEFAULT_SHIJI_PROFILE,
        "requested_profile": profile,
        "shiji": witness["shiji"] if witness else rotation["derived_shiji"],
        "guest_count_override": (
            witness["guest_count"]
            if witness and profile == "jinjing_vol3_table_literal_v1"
            else None
        ),
    }


def cyclic_core(
    accumulation: int,
    *,
    yin: bool = False,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    """Compute Taiyi 72-ju core with optional Vol. 3 printed-table policy."""
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("太乙积数必须是正整数")
    if table_policy not in TAIYI_TABLE_POLICIES:
        raise ValueError("table_policy仅支持computed或printed_table")

    ju = (accumulation - 1) % 72 + 1
    taiyi_number = (1, 2, 3, 4, 6, 7, 8, 9)[((accumulation - 1) % 24) // 3]
    eyes_cycle = "申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤"
    eyes = eyes_cycle[(accumulation - 1) % 18]
    if yin:
        taiyi_number = 10 - taiyi_number
        eyes = RING[(RING.index(eyes) + 8) % 16]
    jishen = BRANCHES[((8 if yin else 2) - (accumulation - 1)) % 12]

    effective_shiji_profile = (
        "jinjing_vol3_table_literal_v1"
        if table_policy == "printed_table" and shiji_profile is None
        else shiji_profile
    )
    starting_spirit = resolve_shiji_variant(
        yin=yin,
        ju=ju,
        wenchang=eyes,
        jishen=jishen,
        shiji_profile=effective_shiji_profile,
    )
    shiji = starting_spirit["shiji"]
    override = (
        VOL3_PRINTED_TABLE_OVERRIDES.get((yin, ju), {})
        if table_policy == "printed_table"
        else {}
    )
    if "shiji" in override:
        shiji = override["shiji"]

    home = count_to_taiyi(eyes, taiyi_number)
    guest = count_to_taiyi(shiji, taiyi_number)

    main_count = override.get("main_count", home["count"])
    printed_guest_count = override.get(
        "guest_count", starting_spirit["guest_count_override"]
    )
    guest_count = guest["count"] if printed_guest_count is None else printed_guest_count

    home_trace: dict[str, Any] = dict(home)
    if "main_count" in override:
        home_trace.update(
            selected_count=main_count,
            selected_count_basis="卷三原表字面（printed_table）",
        )
    guest_trace: dict[str, Any] = dict(guest)
    if printed_guest_count is not None:
        guest_trace.update(
            selected_count=guest_count,
            selected_count_basis="卷三原表字面（printed_table）",
        )

    main_general = general_for_count(main_count)
    guest_general = general_for_count(guest_count)
    return {
        "accumulation": accumulation,
        "yin_dun": yin,
        "kook_number": ju,
        "main_calculation": f"{'陰' if yin else '陽'}遁{chinese_numeral(ju)}局",
        "table_policy": table_policy,
        "taiyi_number": taiyi_number,
        "taiyi_palace": PALACES[taiyi_number],
        "wenchang_palace": eyes,
        "jishen": jishen,
        "shiji": shiji,
        "shiji_profile": starting_spirit["profile"],
        **(
            {"requested_shiji_profile": starting_spirit["requested_profile"]}
            if starting_spirit["requested_profile"] != starting_spirit["profile"]
            else {}
        ),
        "main_count": main_count,
        "guest_count": guest_count,
        "main_count_des": count_labels(main_count),
        "guest_count_des": count_labels(guest_count),
        "main_general": main_general,
        "guest_general": guest_general,
        "main_vice_general": main_general * 3 % 10,
        "guest_vice_general": guest_general * 3 % 10,
    }


GENERAL_FIELDS = {
    "main_general": "主大将",
    "main_vice_general": "主参将",
    "guest_general": "客大将",
    "guest_vice_general": "客参将",
}


def principal_enclosures(core: dict[str, Any]) -> list[dict[str, Any]]:
    ring = [PALACES[n] for n in PALACE_ORDER]
    taiyi = core["taiyi_palace"]
    index = ring.index(taiyi)
    targets = {
        "wenchang_palace": ("文昌", core["wenchang_palace"]),
        "shiji": ("始击", core["shiji"]),
        **{f: (lbl, PALACES[core[f]]) for f, lbl in GENERAL_FIELDS.items()},
    }

    def fact(field: str) -> dict[str, Any]:
        return {
            "field": (
                field
                if field in {"taiyi_palace", "wenchang_palace"}
                else "core_board." + field
            ),
            "value": core[field],
        }

    patterns = []
    for field, label in GENERAL_FIELDS.items():
        end = PALACES[core[field]]
        if end not in ring:
            continue
        distance = (ring.index(end) - index) % 8
        if distance not in (2, 6):
            continue
        middle = ring[(index + (1 if distance == 2 else -1)) % 8]
        for target, (subject, palace) in targets.items():
            if target == field or palace != middle:
                continue
            patterns.append(
                {
                    "name": "提挟",
                    "subject": subject,
                    "variant": f"太乙与{label}夹{subject}于正宫",
                    "basis": [fact("taiyi_palace"), fact(field), fact(target)],
                    "traditional_meaning": f"太乙{taiyi}与{label}{end}从相邻两侧夹{subject}{middle}",
                }
            )
    return patterns


def eye_general_relations(core: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = []
    for field, label in GENERAL_FIELDS.items():
        number = core[field]
        palace = PALACES[number]
        general = {"field": "core_board." + field, "value": number}
        if palace == core["wenchang_palace"]:
            patterns.append(
                {
                    "name": "关",
                    "subject": label,
                    "variant": f"{label}与文昌同宫",
                    "basis": [general, {"field": "wenchang_palace", "value": palace}],
                    "traditional_meaning": f"{label}{palace}与文昌{palace}同宫，主客将目关",
                }
            )
        if palace == core["shiji"]:
            patterns.append(
                {
                    "name": "掩",
                    "subject": "始击",
                    "variant": f"始击掩{label}",
                    "basis": [{"field": "core_board.shiji", "value": palace}, general],
                    "traditional_meaning": f"始击{palace}与{label}{palace}同宫，始击掩将",
                }
            )
    return patterns


def structural_patterns(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate classical Taiyi spatial conditions (掩/囚/对/格/击/迫/关/提挟)."""
    taiyi = core["taiyi_palace"]
    center = RING.index(taiyi)
    opposite = RING[(center + 8) % 16]
    positions = {"wenchang_palace": core["wenchang_palace"], "shiji": core["shiji"]}
    labels = {
        "wenchang_palace": "文昌",
        "shiji": "始击",
        **GENERAL_FIELDS,
    }
    for field in GENERAL_FIELDS:
        positions[field] = PALACES[core[field]]
    result: list[dict[str, Any]] = []

    def fact(field: str) -> dict[str, Any]:
        return {
            "field": (
                field
                if field in {"wenchang_palace", "taiyi_palace"}
                else "core_board." + field
            ),
            "value": core[field],
        }

    def add(
        name: str,
        subject: str,
        meaning: str,
        *,
        other: str = "taiyi_palace",
        variant: str | None = None,
    ) -> None:
        result.append(
            {
                "name": name,
                "subject": labels[subject],
                "variant": variant or name,
                "basis": [fact(subject), fact(other)],
                "traditional_meaning": meaning,
            }
        )

    for field, palace in positions.items():
        if palace == taiyi:
            if field == "shiji":
                add("掩", field, "始击与太乙同宫")
            else:
                add("囚", field, f"{labels[field]}与太乙同宫")
        if palace == opposite:
            if field == "wenchang_palace":
                add("对", field, "文昌与太乙对宫")
            elif field in {"shiji", "guest_general", "guest_vice_general"}:
                add("格", field, f"{labels[field]}与太乙对宫")
        if palace not in RING:
            continue
        distance = (RING.index(palace) - center) % 16
        if distance not in (1, 2, 14, 15):
            continue
        forward = distance in (1, 2)
        adjacent_spirit = distance in (1, 15)
        if field == "shiji":
            variant = (
                ("前击" if forward else "后击")
                if adjacent_spirit
                else ("外宫击" if forward else "内宫击")
            )
            add(
                "击",
                field,
                f"始击在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                variant=variant,
            )
        else:
            variant = ("外" if forward else "内") + (
                "辰迫" if adjacent_spirit else "宫迫"
            )
            add(
                "迫",
                field,
                f"{labels[field]}在太乙{'前' if forward else '后'}一{'辰' if adjacent_spirit else '宫'}",
                variant=variant,
            )
    for main in ("main_general", "main_vice_general"):
        for guest in ("guest_general", "guest_vice_general"):
            if positions[main] == positions[guest]:
                add("关", main, f"{labels[main]}与{labels[guest]}同宫", other=guest)

    result.extend(principal_enclosures(core))
    result.extend(eye_general_relations(core))
    return result


CLAUSES = (
    ("shiji_clear", "始击无掩击", {"始击"}, {"掩", "击"}),
    ("wenchang_clear", "文昌无囚迫", {"文昌"}, {"囚", "迫"}),
    (
        "generals_unconnected",
        "主客大小将无相关",
        {"主大将", "主参将", "客大将", "客参将"},
        {"关"},
    ),
)


def conjunction(*values: bool | None) -> bool | None:
    if not values or any(v is not None and type(v) is not bool for v in values):
        raise ValueError("条件合取需要非空的布尔或未知值")
    if any(v is False for v in values):
        return False
    return None if any(v is None for v in values) else True


def five_general_conditions(
    patterns: list[dict[str, Any]], *, core: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Complete Vol. 4 五将发 adjudication from evaluated spatial patterns."""
    clauses: list[dict[str, Any]] = []
    for key, label, subjects, names in CLAUSES:
        blockers = [
            {
                "source_path": f"patterns.{i}",
                "name": pattern["name"],
                "subject": pattern["subject"],
                "variant": pattern["variant"],
            }
            for i, pattern in enumerate(patterns)
            if pattern.get("subject") in subjects and pattern.get("name") in names
        ]
        satisfied = not blockers
        clauses.append(
            {
                "id": key,
                "label": label,
                "satisfied": satisfied,
                "assessed_satisfied": satisfied,
                "blockers": blockers,
                "unassessed": [],
            }
        )
    all_ok = all(bool(clause["satisfied"]) for clause in clauses)
    return {
        "conditions_satisfied": all_ok,
        "assessed_conditions_satisfied": all_ok,
        "same_core_coverage_checked": core is not None,
        "clauses": clauses,
    }


def _adjudication_label(
    five_ok: bool | None, gates_ok: bool | None, core: dict[str, Any]
) -> str:
    du_sai = (core.get("main_count", 0) % 10 == 5) or (
        core.get("guest_count", 0) % 10 == 5
    )
    if five_ok is True and gates_ok is True:
        return "门具将发（数逢杜塞）" if du_sai else "门具将发"
    if five_ok is True and gates_ok is False:
        return "将发门不具（杜塞）" if du_sai else "门不具"
    if five_ok is False and gates_ok is True:
        return "门具将不发（杜塞）" if du_sai else "将不发"
    if five_ok is False and gates_ok is False:
        return "门不具将不发（杜塞）"
    return "待定"


def update_conjunction(
    assessment: dict[str, Any], core: dict[str, Any] | None = None
) -> None:
    five = assessment["five_generals"]["conditions_satisfied"]
    gates = assessment["three_gates"].get("conditions_satisfied")
    combined = conjunction(five, gates)
    assessment["menju_jiangfa"] = combined
    adjudication = _adjudication_label(five, gates, core or {})
    assessment["adjudication"] = adjudication
    words = {True: "满足", False: "不满足", None: "未定"}
    assessment["summary"] = (
        f"五将三项{words[five]}，三门条件{words[gates]}；判定：{adjudication}。"
    )


def gate_cycle(accumulation: int) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1:
        raise ValueError("太乙八门积数必须是正整数")
    phase = (accumulation - 1) % 240
    index, in_gate = divmod(phase, 30)
    return {
        "accumulation": accumulation,
        "cycle_length": 240,
        "cycle_unit": "selected_count_unit",
        "cycle_position": phase + 1,
        "units_per_gate": 30,
        "gate_index": index,
        "unit_in_gate": in_gate + 1,
        "duty_gate": DOORS[index],
    }


def key_hour_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("金钥匙四门须完整正整数积时及明确阴阳遁")
    phase = (accumulation - 1) % 120
    index, in_gate = divmod(phase, 30)
    doors = tuple("杜死伤景") if yin else tuple("开生惊休")
    return {
        "accumulation": accumulation,
        "cycle_length": 120,
        "cycle_unit": "double_hour",
        "cycle_position": phase + 1,
        "units_per_gate": 30,
        "gate_index": index,
        "unit_in_gate": in_gate + 1,
        "duty_gate": doors[index],
    }


def key_day_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    result = key_hour_gate_cycle(accumulation, yin)
    result.update(cycle_unit="day", source_modulus=240)
    return result


def gate_frame(
    anchor: int, duty_gate: str, anchor_path: str, source_position: str | None = None
) -> dict[str, Any]:
    if type(anchor) is not int or anchor not in PALACES or duty_gate not in DOORS:
        raise ValueError("太乙门盘需要实际宫位和已知直门")
    if anchor == 5:
        return {
            "status": "not_assessed",
            "anchor_number": 5,
            "anchor_palace": "中",
            "anchor_source_path": anchor_path,
            "anchor_source_value": 5,
            "reason": "中五无八方环位，不布外门。",
        }
    start = PALACE_ORDER.index(anchor)
    door_start = DOORS.index(duty_gate)
    rows = [
        {
            "number": number,
            "palace": PALACES[number],
            "door": DOORS[(door_start + i - start) % 8],
            "spirit_positions": [s for s in RING if SECTORS[s] == number],
        }
        for i, number in enumerate(PALACE_ORDER)
    ]
    return {
        "status": "computed",
        "anchor_number": anchor,
        "anchor_palace": PALACES[anchor],
        "anchor_source_path": anchor_path,
        "anchor_source_value": (
            source_position if source_position is not None else anchor
        ),
        "duty_gate": duty_gate,
        "rows": rows,
    }


def check_three_gates(
    frame: dict[str, Any], entities: list[dict[str, Any]], path: str
) -> dict[str, Any]:
    if frame["status"] != "computed":
        return {
            "status": "not_assessed",
            "reason": frame["reason"],
            "conditions_satisfied": None,
            "frame_source_path": path,
        }
    checks = []
    rows = frame["rows"]
    for entity in entities:
        sector = SECTORS[entity["position"]]
        i, row = next((i, r) for i, r in enumerate(rows) if r["number"] == sector)
        door = row["door"]
        checks.append(
            {
                **entity,
                "sector_number": sector,
                "door": door,
                "gate_source_path": f"{path}.rows.{i}",
                "obstructs": door in GOOD_DOORS,
                "incomplete_kind": (
                    "三门不具"
                    if door == "休"
                    else "两门不具" if door in {"开", "生"} else None
                ),
            }
        )
    return {
        "status": "computed",
        "conditions_satisfied": not any(c["obstructs"] for c in checks),
        "checks": checks,
        "frame_source_path": path,
    }


def determinate_calculation(board: dict[str, Any], mode: str) -> dict[str, Any]:
    """Rotate 文昌 by (直支 - 合神) steps around the 16-spirit ring (定计/定目)."""
    core = board["core_board"]
    ruler = core["suijun"] if mode in {"year", "fate"} else core["ruler_branch"]
    hegod = core["heshen"]
    eyes = board["wenchang_palace"]
    shift = (RING.index(ruler) - RING.index(hegod)) % 16
    marker = RING[(RING.index(eyes) + shift) % 16]
    trace = count_to_taiyi(marker, core["taiyi_number"])
    general = general_for_count(trace["count"])
    vice = general * 3 % 10
    core.update(
        dingmu=marker,
        set_count=trace["count"],
        set_general=general,
        set_vice_general=vice,
    )
    return {
        "status": "computed",
        "marker": marker,
        "count": trace["count"],
        "general": general,
        "vice_general": vice,
        "rotation": {
            "ruler_branch": ruler,
            "hegod": hegod,
            "wenchang": eyes,
            "forward_steps": shift,
        },
    }


def attach_gate_board(
    board: dict[str, Any], mode: str, year: int | None = None
) -> None:
    if mode not in {"year", "month", "day", "hour", "minute", "fate"}:
        raise ValueError("太乙八门仅接受year/month/day/hour/minute/fate计法")
    core = board["core_board"]
    determinate = determinate_calculation(board, mode)
    board["determinate_calculation"] = determinate

    marks = {
        p["palace"]: p["markers"]
        for p in board["palace_marks"] + [board["center_marks"]]
    }
    for label, position in (
        ("定目", determinate["marker"]),
        ("定大", PALACES[determinate["general"]]),
        ("定参", PALACES[determinate["vice_general"]]),
    ):
        if label not in marks[position]:
            marks[position].append(label)

    rules = board.get("calendar_rules", {})
    is_key_month = (
        mode == "month" and rules.get("month_profile") == "key_month_tianzheng_jie_v1"
    )
    is_key_day = mode == "day" and rules.get("day_profile") == "key_day_winter_jiazi_v1"
    is_key_hour = (
        mode == "hour" and rules.get("hour_profile") == "key_hour_winter_jiazi_v1"
    )

    entities = [
        {
            "label": "太乙",
            "source_path": "taiyi.taiyi_palace",
            "position": board["taiyi_palace"],
        },
        {
            "label": "文昌",
            "source_path": "taiyi.wenchang_palace",
            "position": board["wenchang_palace"],
        },
    ]

    if is_key_month or is_key_day or is_key_hour:
        key_profile = (
            "key_month_eight_gates_240_v1"
            if is_key_month
            else (
                "key_day_four_gates_120_v1"
                if is_key_day
                else "key_hour_four_gates_120_v1"
            )
        )
        if is_key_month:
            counter = gate_cycle(core["accumulation"])
            counter.update(
                cycle_unit="solar_month",
                remaining_units_after_current=30 - counter["unit_in_gate"],
            )
        else:
            counter = (key_day_gate_cycle if is_key_day else key_hour_gate_cycle)(
                core["accumulation"], board["rotation"] == "逆布"
            )
        moving = gate_frame(
            SECTORS[determinate["marker"]],
            counter["duty_gate"],
            "taiyi.core_board.dingmu",
            determinate["marker"],
        )
        selected_check = check_three_gates(moving, entities, "taiyi.gates.moving_frame")
        board["gates"] = {
            "status": "computed",
            "reason": None,
            "calculation_mode": mode,
            "selected_profile": key_profile,
            "counter": counter,
            "moving_frame": moving,
            "old_open_frames": None,
            "old_open_summary": None,
            "dingmu_comparison_frame": None,
            "ruleset": {
                "id": key_profile,
                "version": "2.0.0",
                "author": "FateBridge contributors",
                "classical_author": "太乙金钥匙续集",
                "sector_rule_id": "jinjing_four_cardinals_four_corners_v1",
                "classical_conformance": "implemented",
                "classical_acceptance_passed": True,
            },
        }
        board["condition_assessment"]["three_gates"] = selected_check
        update_conjunction(board["condition_assessment"], core)
        return

    gate_accum = (
        3361 + year - 724
        if mode in {"year", "fate"} and year is not None
        else core["accumulation"]
    )
    unit_map = {
        "year": "year",
        "fate": "year",
        "month": "solar_month",
        "day": "day",
        "hour": "double_hour",
        "minute": "quarter_hour",
    }
    counter = gate_cycle(gate_accum)
    counter["cycle_unit"] = unit_map[mode]
    moving = gate_frame(
        core["taiyi_number"], counter["duty_gate"], "taiyi.core_board.taiyi_number"
    )
    selected_check = check_three_gates(moving, entities, "taiyi.gates.moving_frame")
    old_frames: dict[str, Any] = {}
    if mode in {"year", "fate"}:
        for key, field, targets in (
            ("taiyi", "taiyi_number", entities[1:]),
            ("main", "main_general", entities),
            (
                "guest",
                "guest_general",
                [
                    entities[0],
                    {
                        "label": "始击",
                        "source_path": "taiyi.core_board.shiji",
                        "position": core["shiji"],
                    },
                ],
            ),
            ("determinate", "set_general", entities),
        ):
            frame = gate_frame(core[field], "开", "taiyi.core_board." + field)
            frame["three_gates"] = check_three_gates(
                frame, targets, "taiyi.gates.old_open_frames." + key
            )
            old_frames[key] = frame

    profile_map = {
        "year": "wang_annual_240",
        "fate": "wang_annual_240",
        "month": "wang_month_240",
        "day": "wang_day_240",
        "hour": "wang_hour_240",
        "minute": "wang_minute_240",
    }
    board["gates"] = {
        "status": "computed",
        "reason": None,
        "calculation_mode": mode,
        "selected_profile": profile_map[mode],
        "counter": counter,
        "moving_frame": moving,
        "old_open_frames": old_frames or None,
        "old_open_summary": (
            {
                key: {
                    **{k: v for k, v in frame.items() if k != "rows"},
                    "source_path": "taiyi.gates.old_open_frames." + key,
                }
                for key, frame in old_frames.items()
            }
            if old_frames
            else None
        ),
        "dingmu_comparison_frame": gate_frame(
            SECTORS[determinate["marker"]],
            counter["duty_gate"],
            "taiyi.core_board.dingmu",
            determinate["marker"],
        ),
        "ruleset": {
            "id": "jinjing_wang_gates_240_v2",
            "version": "2.0.0",
            "author": "FateBridge contributors",
            "classical_author": "唐·王希明",
            "sector_rule_id": "jinjing_four_cardinals_four_corners_v1",
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        },
    }
    board["condition_assessment"]["three_gates"] = selected_check
    update_conjunction(board["condition_assessment"], core)


COUNTER_UNITS = {
    "year": "年",
    "month": "节月",
    "day": "日",
    "hour": "时辰",
    "minute": "刻",
    "fate": "年",
}


class CounterGroup(TypedDict):
    number: int
    position: int
    size: int


class CounterCycles(TypedDict):
    ruleset_id: str
    version: str
    paths_relative_to: str
    counter_path: str
    actual_ju_path: str
    calculation_mode: str
    counter_unit: str
    counter: int
    completed_cycles_before_current360: int
    position360: int
    actual_kook_number: int
    ji60: CounterGroup
    yuan72: CounterGroup


def counter_cycles(
    core: Mapping[str, object], *, calculation_mode: str | None
) -> CounterCycles:
    mode = "year" if calculation_mode is None else calculation_mode
    counter, ju = core.get("accumulation"), core.get("kook_number")
    if (
        type(counter) is not int
        or counter < 1
        or type(ju) is not int
        or not 1 <= ju <= 72
        or not isinstance(mode, str)
        or mode not in COUNTER_UNITS
    ):
        raise ValueError("太乙周期分解需要同盘正整数完整计数、实际局号和明确计量单位")
    completed, offset = divmod(counter - 1, 360)
    ji, within_ji = divmod(offset, 60)
    yuan, within_yuan = divmod(offset, 72)
    if within_yuan + 1 != ju:
        raise ValueError("太乙同盘完整计数的72周期位与实际局号不一致")
    return {
        "ruleset_id": "taiyi_selected_counter_cycles_v2",
        "version": "2.0.0",
        "paths_relative_to": "taiyi_board",
        "counter_path": "core_board.accumulation",
        "actual_ju_path": "core_board.kook_number",
        "counter": counter,
        "calculation_mode": mode,
        "counter_unit": COUNTER_UNITS[mode],
        "completed_cycles_before_current360": completed,
        "position360": offset + 1,
        "ji60": {"number": ji + 1, "position": within_ji + 1, "size": 60},
        "yuan72": {"number": yuan + 1, "position": within_yuan + 1, "size": 72},
        "actual_kook_number": ju,
    }


def counter_cycles_text(cycles: CounterCycles) -> str:
    ji, yuan = cycles["ji60"], cycles["yuan72"]
    return (
        f"周期计数：{cycles['counter']}{cycles['counter_unit']}，"
        f"整周{cycles['completed_cycles_before_current360']}，"
        f"周内第{cycles['position360']}位；第{ji['number']}纪第{ji['position']}，"
        f"第{yuan['number']}元第{yuan['position']}，局号{cycles['actual_kook_number']}。"
    )


# ---------------------------------------------------------------------------
# Annual Ten Spirits / Long Cycles (卷五 三基五福大小游四神)
# ---------------------------------------------------------------------------

LONG_RULESET_ID = "jinjing_annual_ten_markers_v1"
LONG_BRANCH_SEQUENCE = tuple("戌亥子丑寅卯辰巳午未申酉")
TWELVE_PALACES = tuple("123456789") + ("绛", "明", "玉")
REFERENCE_YEAR = 724
SANJI_REFERENCE = 285011
LONG_CYCLE_REFERENCE = 13331
SHORT_CYCLE_REFERENCE = 3361
FOUR_ORIGINS = {"sishen": "1", "tianyi": "6", "diyi": "9", "zhifu": "5"}
LONG_LABELS = {
    "junji": "君基",
    "chenji": "臣基",
    "minji": "民基",
    "wufu": "五福",
    "dayou": "大游",
    "dayou_tianmu": "大游天目",
    "xiaoyou": "小游",
    "sishen": "四神",
    "tianyi": "天乙",
    "diyi": "地乙",
    "zhifu": "直符",
}
LONG_SECTIONS = {
    "junji": "推君基太乙法",
    "chenji": "推臣基太乙法",
    "minji": "推民基太乙法",
    "wufu": "推五福太乙法",
    "dayou": "推大遊太乙所在",
    "dayou_tianmu": "推大遊天目所在法",
    "xiaoyou": "推小遊太乙積年法",
    "sishen": "推四神太乙法",
    "tianyi": "推天乙太乙法",
    "diyi": "四神三元五紀立成",
    "zhifu": "推直符太乙法",
}


class AnnualMarker(TypedDict):
    position: str
    palace: str
    accumulation: int
    cycle_length: int
    cycle_year: int
    years_per_position: int
    position_index: int
    year_in_palace: int
    palace_number: int | None
    space: Literal[
        "taiyi_nine_palaces", "three_extra_palaces_unmapped", "sixteen_palaces"
    ]
    label: NotRequired[str]
    source_section: NotRequired[str]
    epoch_id: NotRequired[str]
    classical_palace_name: NotRequired[str]
    administration_phase: NotRequired[str]
    table_position: NotRequired[str]
    table_disagreement: NotRequired[bool]


@lru_cache(maxsize=1)
def _vol5_table() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "data/classical/taiyi-jinjing-vol5-v1.json"
    )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _rotated(sequence: tuple[str, ...], start: str) -> tuple[str, ...]:
    idx = sequence.index(start)
    return sequence[idx:] + sequence[:idx]


def _moving_marker(
    accumulation: int, sequence: tuple[str, ...], years_per_position: int
) -> AnnualMarker:
    if type(accumulation) is not int or accumulation < 1:
        raise ValueError("太乙年运积数必须是正整数")
    cycle_length = len(sequence) * years_per_position
    offset = (accumulation - 1) % cycle_length
    index, in_position = divmod(offset, years_per_position)
    position = sequence[index]
    number = int(position) if position.isdigit() else None
    if number is not None:
        palace = PALACES[number]
        space: Literal[
            "taiyi_nine_palaces", "three_extra_palaces_unmapped", "sixteen_palaces"
        ] = "taiyi_nine_palaces"
    elif position in {"绛", "明", "玉"}:
        palace = {"绛": "绛宫", "明": "明堂", "玉": "玉堂"}[position]
        space = "three_extra_palaces_unmapped"
    else:
        palace = position
        space = "sixteen_palaces"
    return {
        "position": position,
        "palace": palace,
        "palace_number": number,
        "space": space,
        "accumulation": accumulation,
        "cycle_length": cycle_length,
        "cycle_year": offset + 1,
        "years_per_position": years_per_position,
        "position_index": index,
        "year_in_palace": in_position + 1,
    }


def annual_long_cycles(year: int) -> dict[str, Any]:
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError("太乙年运需要1至9999之间的整数公元年份")
    elapsed = year - REFERENCE_YEAR
    sanji = SANJI_REFERENCE + elapsed
    long_count = LONG_CYCLE_REFERENCE + elapsed
    short_count = SHORT_CYCLE_REFERENCE + elapsed

    table = _vol5_table()
    phase = (short_count - 1) % 180
    yuan = ("upper", "middle", "lower")[phase // 60]
    row = table["rows"][phase % 60]

    four_spirits: dict[str, AnnualMarker] = {}
    for name, start in FOUR_ORIGINS.items():
        rec = _moving_marker(short_count, _rotated(TWELVE_PALACES, start), 3)
        rec["table_position"] = row["expected"][f"{name}.{yuan}"]
        rec["table_disagreement"] = rec["table_position"] != rec["position"]
        four_spirits[name] = rec

    records: dict[str, AnnualMarker] = {
        "junji": _moving_marker(sanji, LONG_BRANCH_SEQUENCE, 30),
        "chenji": _moving_marker(sanji, LONG_BRANCH_SEQUENCE, 3),
        "minji": _moving_marker(sanji, LONG_BRANCH_SEQUENCE, 1),
        "wufu": _moving_marker(long_count, ("1", "3", "9", "7", "5"), 45),
        "dayou": _moving_marker(long_count, tuple("78912346"), 36),
        "dayou_tianmu": _moving_marker(
            long_count, tuple("未坤坤申酉戌乾乾亥子丑艮寅卯辰巽巳午"), 1
        ),
        "xiaoyou": _moving_marker(short_count, tuple("12346789"), 3),
        **four_spirits,
    }
    for marker_name, record in records.items():
        record["label"] = LONG_LABELS[marker_name]
        record["source_section"] = LONG_SECTIONS[marker_name]
        record["epoch_id"] = (
            "sanji"
            if marker_name in {"junji", "chenji", "minji"}
            else (
                "long_you_wufu"
                if marker_name in {"wufu", "dayou", "dayou_tianmu"}
                else "short_you_spirits"
            )
        )
    wufu_names = {"1": "黄秘", "3": "黄始", "9": "黄室", "7": "黄庭", "5": "玄师"}
    records["wufu"]["classical_palace_name"] = wufu_names[records["wufu"]["position"]]
    records["dayou"]["administration_phase"] = ("治天", "治地", "治人")[
        (records["dayou"]["year_in_palace"] - 1) // 12
    ]
    return {
        "status": "computed",
        "year": year,
        "time_granularity": "year",
        "ruleset": {
            "id": LONG_RULESET_ID,
            "version": "2.0.0",
            "author": "FateBridge contributors",
            "classical_author": "唐·王希明",
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        },
        "epochs": {
            "sanji": {
                "year": REFERENCE_YEAR,
                "accumulation": SANJI_REFERENCE,
                "equivalent_short_epoch_accumulation": 611,
                "equivalence_modulus": 360,
            },
            "long_you_wufu": {
                "year": REFERENCE_YEAR,
                "accumulation": LONG_CYCLE_REFERENCE,
            },
            "short_you_spirits": {
                "year": REFERENCE_YEAR,
                "accumulation": SHORT_CYCLE_REFERENCE,
            },
        },
        "counting_convention": "积数含本年；每宫满行率后次年换宫；三元五纪按连续180年计。",
        "records": records,
    }


def long_cycle_text(cycles: dict[str, Any] | None) -> str:
    if cycles is None or cycles.get("status") == "not_computed_for_selected_mode":
        return "非年计未附年度十神。"
    lines = [f"卷五年度巡行：{cycles['year']}。"]
    for r in cycles["records"].values():
        lines.append(f"{r['label']}：{r['palace']}（第{r['year_in_palace']}年）")
    return "\n".join(lines)


def attach_long_cycles(board: dict[str, Any], year: int) -> None:
    cycles = annual_long_cycles(year)
    board["long_cycles"] = cycles
    board["long_cycle_summary"] = {
        "status": "computed",
        "time_granularity": "year",
        "year": year,
        "ruleset_id": LONG_RULESET_ID,
        "positions": {
            r["label"]: f"{r['palace']}／第{r['year_in_palace']}年"
            for r in cycles["records"].values()
        },
    }
    positions = {row["palace"]: row["markers"] for row in board["palace_marks"]}
    positions["中"] = board["center_marks"]["markers"]
    extra: dict[str, list[str]] = {}
    for record in cycles["records"].values():
        label = record["label"]
        if record["palace"] in positions:
            positions[record["palace"]].append(label)
        else:
            extra.setdefault(record["palace"], []).append(label)
    for marks in positions.values():
        marks.sort()
    board["extra_palace_marks"] = [
        {"palace": palace, "markers": sorted(marks)} for palace, marks in extra.items()
    ]


# ---------------------------------------------------------------------------
# Key Ten Essences (金钥匙十精)
# ---------------------------------------------------------------------------


def _held_ring(start: str, held: str) -> tuple[str, ...]:
    ring = RING[RING.index(start) :] + RING[: RING.index(start)]
    return tuple(
        p for position in ring for p in [position] * (2 if position in held else 1)
    )


def key_ten_jing(accumulation: int, yin: bool) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("金钥匙十精须正整数积数及明确阴阳遁")
    sequences = {
        "emperor": ("天皇", _held_ring("申", "乾艮巽坤"), "武德起，四维重留"),
        "earth": ("地符", _held_ring("戌", "子午卯酉"), "阴主起，四正重留"),
        "heaven_time": (
            "天时",
            tuple("寅卯辰巳午未申酉戌亥子丑"),
            "吕申寅起顺行十二支",
        ),
        "flying_bird": (
            "飞鸟",
            tuple(PALACES[n] for n in range(1, 10)),
            "一宫起顺行九宫",
        ),
        "heaven_venerable": ("天尊", tuple("子酉午卯"), "八宫起逆行四正"),
        "five_elements": ("五行", tuple("乾子艮巽坤"), "乾子艮巽坤五位"),
        "eight_winds": (
            "八风",
            tuple(PALACES[n] for n in (2, 3, 4, 5, 6, 7, 8, 9, 1)),
            "二宫起顺行九宫",
        ),
        "five_winds": (
            "五风",
            tuple(PALACES[n] for n in (1, 3, 5, 7, 9, 2, 4, 6, 8)),
            "一三五七九二四六八",
        ),
        "three_winds": (
            "三风",
            tuple(PALACES[n] for n in (3, 7, 2, 6, 1, 5, 9, 4, 8)),
            "三七二六一五九四八",
        ),
    }
    records: dict[str, Any] = {}
    numbers = {v: k for k, v in PALACES.items()}
    for key, (label, sequence, rule) in sequences.items():
        phase = (accumulation - 1) % len(sequence)
        yang_pos = sequence[phase]
        palace: str | None = yang_pos
        if yin:
            palace = None if yang_pos == "中" else RING[(RING.index(yang_pos) + 8) % 16]
        records[key] = {
            "label": label,
            "status": "computed" if palace is not None else "not_assessed",
            "palace": palace,
            "palace_number": numbers.get(palace) if palace is not None else None,
            "yang_position": yang_pos,
            "period": len(sequence),
            "cycle_position": phase + 1,
            "rule": rule,
        }
    return {
        "status": "computed",
        "accumulation": accumulation,
        "yin": yin,
        "records": records,
        "ruleset_id": "key_day_ten_jing_v2",
        "version": "2.0.0",
        "author": "FateBridge contributors",
        "classical_author": "太乙金钥匙续集",
        "classical_acceptance_passed": True,
    }


def ten_jing_text(ten_jing: dict[str, Any]) -> str:
    return "；".join(
        f"{r['label']}:{r['palace'] or '中'}" for r in ten_jing["records"].values()
    )


# ---------------------------------------------------------------------------
# Shiji derivation text & Noble source check (used by local_techniques & core)
# ---------------------------------------------------------------------------


def shiji_derivation(core: dict[str, Any]) -> dict[str, Any]:
    wenchang = core.get("wenchang_palace")
    jishen = core.get("jishen")
    actual = core.get("shiji")
    if (
        type(wenchang) is not str
        or wenchang not in RING
        or type(jishen) is not str
        or jishen not in BRANCHES
        or type(actual) is not str
        or actual not in RING
    ):
        return {"status": "not_assessed", "reason": "文昌、计神或始击无效"}
    rotation = rotate_shiji(wenchang, jishen)
    return {
        "status": "computed_from_actual_inputs",
        "shiji_profile": str(core.get("shiji_profile") or DEFAULT_SHIJI_PROFILE),
        **rotation,
        "actual_shiji": actual,
        "matches_actual": rotation["derived_shiji"] == actual,
    }


def shiji_derivation_text(assessment: dict[str, Any]) -> str:
    if assessment.get("status") == "not_assessed":
        return str(assessment.get("reason", ""))
    return (
        f"计神{assessment['jishen']}加和德艮顺行{assessment['step_count']}步至"
        f"{assessment['wenchang']}得{assessment['derived_shiji']}（实取{assessment['actual_shiji']}）。"
    )


@lru_cache(maxsize=1)
def _dangshi_catalog() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "data/classical/taiyi-dangshi-nobles-v1.json"
    )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def noble_source_assessment(
    day_stem: str, liureng: dict[str, Any], *, taiyi_mode: str
) -> dict[str, Any]:
    """Compare the run's Liuren noble start with 金镜当时贵人 tables."""
    catalog = _dangshi_catalog()
    base: dict[str, Any] = {
        "status": "not_assessed",
        "ruleset_id": catalog["id"],
        "ruleset_version": catalog["version"],
        "taiyi_mode": taiyi_mode,
        "comparisons": [],
    }
    if day_stem not in tuple("甲乙丙丁戊己庚辛壬癸"):
        return {**base, "reason": "日干无效"}
    meta = liureng.get("meta") or {}
    is_day = meta.get("is_diurnal")
    guiren_order = liureng.get("guiren_order")
    if type(is_day) is not bool or not isinstance(guiren_order, str):
        return {**base, "reason": "缺少同盘贵人昼夜与起位信息"}
    start = meta.get("guiren_start_branch")
    if start not in tuple(BRANCHES):
        for row in liureng.get("twelve_board") or []:
            if row.get("god") == "贵人":
                start = row.get("sky_branch")
                break
    if start not in tuple(BRANCHES):
        return {**base, "reason": "未能定位贵人起位"}
    comparisons = []
    for table in catalog["tables"]:
        row = next(r for r in table["rows"] if r["stem"] == day_stem)
        expected = row["morning_branch" if is_day else "evening_branch"]
        comparisons.append(
            {
                "source_id": table["id"],
                "source_edition": table["edition"],
                "source_branch": expected,
                "matches": start == expected,
            }
        )
    return {
        **base,
        "status": "compared_noble_start_only",
        "day_stem": day_stem,
        "is_diurnal": is_day,
        "actual_start_branch": start,
        "comparisons": comparisons,
    }


def noble_source_text(assessment: dict[str, Any]) -> str:
    if assessment.get("status") != "compared_noble_start_only":
        return str(assessment.get("reason", ""))
    return (
        f"{assessment['day_stem']}日{'昼' if assessment['is_diurnal'] else '夜'}"
        f"贵人起{assessment['actual_start_branch']}。"
    )


# ---------------------------------------------------------------------------
# Board Assembly & Summary (Compact, high-speed, zero audit bloat)
# ---------------------------------------------------------------------------


def assemble_board(
    core: dict[str, Any], *, calculation_mode: str | None = None
) -> dict[str, Any]:
    """Assemble the crisp Taiyi board without redundant *source_assessment bloat."""
    marks: dict[str, list[str]] = {palace: [] for palace in DISPLAY_ORDER + "中"}
    placements = {
        "太乙": core["taiyi_palace"],
        "文昌": core["wenchang_palace"],
        "始击": core["shiji"],
        core.get("ruler_label", "太岁"): (
            core["ruler_branch"] if "ruler_branch" in core else core["suijun"]
        ),
        "合神": core["heshen"],
        "计神": core["jishen"],
    }
    for label, field in (
        ("主大", "main_general"),
        ("主参", "main_vice_general"),
        ("客大", "guest_general"),
        ("客参", "guest_vice_general"),
    ):
        placements[label] = PALACES[core[field]]
    for label, palace in placements.items():
        marks[palace].append(label)

    patterns = structural_patterns(core)
    five_cond = five_general_conditions(patterns, core=core)
    return {
        "engine": "fatebridge-offline",
        "counter_cycles": counter_cycles(core, calculation_mode=calculation_mode),
        "taiyi_palace": core["taiyi_palace"],
        "wenchang_palace": core["wenchang_palace"],
        "core_board": {
            **{
                k: v
                for k, v in core.items()
                if k not in {"taiyi_palace", "wenchang_palace", "count_trace"}
            },
            "taiyi_position": f"太乙在{core['taiyi_palace']}宫（{core['taiyi_number']}）",
            "wenchang_position": f"文昌在{core['wenchang_palace']}宫",
        },
        "palace_marks": [
            {"palace": palace, "markers": sorted(marks[palace])}
            for palace in DISPLAY_ORDER
        ],
        "center_marks": {"palace": "中", "markers": sorted(marks["中"])},
        "patterns": patterns,
        "condition_assessment": {
            "ruleset": {
                "id": "jinjing_vol4_five_generals_v2",
                "version": "2.0.0",
                "classical_author": "唐·王希明",
            },
            "five_generals": five_cond,
            "three_gates": {"status": "pending", "conditions_satisfied": None},
            "menju_jiangfa": None,
            "adjudication": "待核三门",
            "summary": "",
        },
        "shiji_derivation": shiji_derivation(core),
        "pattern_summary": {
            "conditions": [
                {"name": p["name"], "subject": p["subject"], "variant": p["variant"]}
                for p in patterns
            ],
            "five_generals_satisfied": five_cond["conditions_satisfied"],
        },
    }


def calendar_summary(board: dict[str, Any]) -> dict[str, Any]:
    calendar = board["calendar_rules"]
    mode = calendar.get("calculation_mode", "year")
    common = {
        "calculation_mode": mode,
        "civil_datetime": calendar["civil_datetime"],
        "timezone": calendar["timezone"],
    }
    if mode in {"year", "fate"}:
        used_lunar = calendar.get("historical_calendar") or calendar.get(
            "civil_lunar_calendar"
        )
        return {
            **common,
            "year": calendar["year"],
            "year_boundary": calendar["year_boundary"],
            "year_boundary_status": calendar["year_boundary_status"],
            **({"used_lunar_date": used_lunar["display"]} if used_lunar else {}),
            **(
                {"year_profile": calendar["year_profile"]}
                if "year_profile" in calendar
                else {}
            ),
        }
    return {
        **common,
        **(
            {
                "anchor_ephemeris_model": board["solar_anchors"]["boundary"][
                    "ephemeris_model"
                ],
                **(
                    {
                        "winter_anchor_ephemeris_model": board["solar_anchors"][
                            "winter_origin"
                        ]["ephemeris_model"]
                    }
                    if "winter_origin" in board["solar_anchors"]
                    else {}
                ),
            }
            if board.get("solar_anchors")
            else {}
        ),
        **{
            key: calendar[key]
            for key in (
                "anchor_name",
                "anchor_utc",
                "counter",
                "clock_basis",
                "hour_profile",
                "month_profile",
                "day_profile",
                "minute_profile",
                "ke_index",
                "input_calendar",
            )
            if key in calendar
        },
    }


# ---------------------------------------------------------------------------
# Taiyi Fate (太乙命法): Twelve Palaces, Life/Body Palaces, 16-Spirit Map
# ---------------------------------------------------------------------------

TWELVE_FATE_PALACE_NAMES = (
    "命宫",
    "兄弟",
    "妻妾",
    "子孙",
    "财帛",
    "田宅",
    "官禄",
    "奴仆",
    "疾厄",
    "福德",
    "相貌",
    "父母",
)


def compute_taiyi_fate_palaces(
    *,
    month_general: str,
    birth_hour_branch: str,
    lunar_year: int,
    gender: str,
) -> dict[str, Any]:
    """Compute《太乙命法》命宫/身宫, 十二命宫, and 行年."""
    mg_idx = BRANCHES.index(month_general)
    hr_idx = BRANCHES.index(birth_hour_branch)
    # Place 月将 on 生时 clockwise; branch at 卯 (idx=3) is 命宫, at 酉 (idx=9) is 身宫.
    life_idx = (mg_idx + (3 - hr_idx)) % 12
    body_idx = (mg_idx + (9 - hr_idx)) % 12
    life_branch = BRANCHES[life_idx]
    body_branch = BRANCHES[body_idx]
    palaces = [
        {"palace": name, "branch": BRANCHES[(life_idx - i) % 12]}
        for i, name in enumerate(TWELVE_FATE_PALACE_NAMES)
    ]
    yang_male = gender == "男"
    # 行年起法：男从丙寅顺行、女从壬申逆行（含命宫起岁参照）
    run_start_branch = "寅" if yang_male else "申"
    return {
        "month_general": month_general,
        "birth_hour_branch": birth_hour_branch,
        "life_palace": life_branch,
        "body_palace": body_branch,
        "twelve_palaces": palaces,
        "run_year_origin_branch": run_start_branch,
        "birth_lunar_year": lunar_year,
    }
