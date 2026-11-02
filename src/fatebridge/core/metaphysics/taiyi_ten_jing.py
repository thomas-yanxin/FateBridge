"""The Key's ten essences, distinct from Jinjing's ten annual markers.

Unresolved literal rules stay unresolved. The day-44 prose and diagram are
source observations, not an instruction to special-case the arithmetic.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import PALACES, RING

from .taiyi_hour import KEY_SOURCE

HEAVEN_TIME_RULE_SOURCES = {
    "key_annual_example": "https://upload.wikimedia.org/wikipedia/commons/1/19/NLC892-411999021066-66022_%E5%A4%AA%E4%B9%99%E9%87%91%E9%91%B0%E5%8C%99.pdf#page=33",
    "jinjing_vol7": "https://zh.wikisource.org/w/index.php?title=太乙金鏡式經_(四庫全書本)/卷07&oldid=773942",
    "tongzong_vol20": "https://www.shidianguji.com/zh/book/CADAL02094393/chapter/1lcppxguguiai",
}


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
            "吕申寅起，顺行十二支，不插入四维",
        ),
        "flying_bird": (
            "飞鸟",
            tuple(PALACES[n] for n in range(1, 10)),
            "一宫起顺行九宫，含中五",
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
        yang_position = sequence[phase]
        palace: str | None = yang_position
        if yin:
            palace = (
                None
                if yang_position == "中"
                else RING[(RING.index(yang_position) + 8) % 16]
            )
        records[key] = {
            "label": label,
            "status": "computed" if palace is not None else "not_assessed",
            "palace": palace,
            "palace_number": numbers.get(palace) if palace is not None else None,
            "yang_position": yang_position,
            "period": len(sequence),
            "cycle_position": phase + 1,
            "sequence": list(sequence),
            "rule": rule,
            "yin_opposition": "阳局所在的十六方对冲" if yin else "阳局不取对冲",
            "reason": (
                "中五无十六方对冲，原文未给寄宫，不自动留中或寄坤。"
                if palace is None
                else None
            ),
            "source": KEY_SOURCE,
        }
    records["heaven_time"].update(
        source_comparisons=[],
        rule_evidence={
            "status": "adopted_rule_with_worked_example_disagreement",
            "basis": "金镜卷七、统宗卷二十均明列十二辰；金钥匙年度例第10数在亥，与寅起十二支一致。本项采纳通则，不据单例倒造十六方周期。",
            "sources": HEAVEN_TIME_RULE_SOURCES,
            "unresolved": "丁未日第8数算路插巽而落坤，与十二支通则不符；原读数保留，未认定为传抄错误或改写原图。",
        },
        candidates=[
            {
                "id": "literal_twelve_branches",
                "yang_position": records["heaven_time"]["yang_position"],
                "adopted": True,
            }
        ],
    )
    if not yin and (accumulation - 1) % 12 == 7:
        records["heaven_time"]["source_comparisons"] = [
            {
                "field": "palace",
                "source_value": "坤",
                "rule_derived_value": records["heaven_time"]["palace"],
                "scope": "图41-42正文与图43丁未课式均作大武坤；仅同一十二支阳局相位的数值对照，历史日期匹配另列。",
                "source": KEY_SOURCE,
            }
        ]
    records["taiyi_ordinal"] = {
        "label": "太乙数",
        "status": "computed_ordinal_only",
        "ordinal": (accumulation - 1) % 72 + 1,
        "palace": None,
        "period": 72,
        "cycle_position": (accumulation - 1) % 72 + 1,
        "reason": "五元七十二局定义与年度例22、日课式44支持局序；日正文又写四宫，宫位语义仍未裁定。阴局对冲不作用于局序。",
        "source": KEY_SOURCE,
    }
    # These reference the same Yang phase, not the same historical date or
    # a separately validated forecast. Keep BOTH source readings.
    records["eight_winds"]["source_comparisons"] = []
    if not yin and (accumulation - 44) % 9 == 0:
        records["eight_winds"]["source_comparisons"] = [
            {
                "source_value": value,
                "rule_derived_value": records["eight_winds"]["palace"],
                "scope": scope,
                "source": KEY_SOURCE,
            }
            for value, scope in (("乾", "图42正文：阴德"), ("艮", "图43课式：三宫"))
        ]
    return {
        "status": "partial_with_source_disagreements",
        "accumulation": accumulation,
        "yin": yin,
        "records": records,
        "source": KEY_SOURCE,
        "ruleset_id": "key_ten_jing_v1",
        "version": "1.1.0",
        "author": "FateBridge contributors",
        "classical_author": "《太乙金钥匙续集》底本题署，作者未独立考定",
        "classical_acceptance_passed": False,
        "scope": "金钥匙十精，不是金镜卷五年度十神；宫位仅依明示规则，未实现天气或事件断语。",
    }


def attach_ten_jing(board: dict[str, Any]) -> None:
    data = key_ten_jing(
        board["core_board"]["accumulation"], board["rotation"] == "逆布"
    )
    board["ten_jing"] = data
    marks = {
        p["palace"]: p["markers"]
        for p in board["palace_marks"] + [board["center_marks"]]
    }
    for record in data["records"].values():
        if record["palace"] is not None:
            marks[record["palace"]].append(record["label"])


def ten_jing_text(data: dict[str, Any]) -> str:
    lines = [f"金钥匙十精：{data['ruleset_id']}；来源：{data['source']}。"]
    for record in data["records"].values():
        location = record.get("palace") or (
            f"第{record['ordinal']}局（非宫位）" if "ordinal" in record else "未裁定"
        )
        lines.append(
            f"{record['label']}：{location}；{record.get('reason') or record.get('rule', '')}。"
        )
        evidence = record.get("rule_evidence")
        if evidence:
            lines.append(
                f"{record['label']}取法依据：{evidence['basis']}；未决：{evidence['unresolved']}；补证来源："
                + "；".join(f"{k}={v}" for k, v in evidence["sources"].items())
            )
        for comparison in record.get("source_comparisons", []):
            lines.append(
                f"{comparison['scope']}作{comparison['source_value']}；本盘规则推算{comparison['rule_derived_value']}，两者并列，未改通则。"
            )
    return "\n".join(lines)
