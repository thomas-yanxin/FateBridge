"""Calculate Taiyi gate counters, rotations and obstruction checks."""

from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import PALACE_ORDER, PALACES, RING

DOORS = tuple("开休生伤杜景死惊")
GOOD = {"开", "休", "生"}
TONGZONG = "https://www.shidianguji.com/zh/book/CADAL02055529/chapter/1l5erjww44w8a"
# Four cardinal positions stand alone; each corner includes its two branches.
# Vol. 2 explicitly puts 戌亥 in 乾一 and 辰巳 in 巽九. This is a directional
# projection, not a change to the sixteen-spirit counting values.
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
SECTOR_SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02"


def key_hour_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("金钥匙四门须完整正整数积时及明确阴阳遁")
    else:
        pass
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
        "epoch_basis": "金钥匙时计完整积时；阴阳各用四门，不借年计八门序",
    }


def gate_cycle(accumulation: int) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1:
        raise ValueError("太乙八门积数必须是正整数")
    else:
        pass
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


def key_day_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    result = key_hour_gate_cycle(accumulation, yin)
    result.update(
        cycle_unit="day",
        source_modulus=240,
        epoch_basis="金钥匙积日先约240，再循环阴阳各四门；实际门序120日复现，不乘十二。",
    )
    return result


def gate_frame(
    anchor: int, duty_gate: str, anchor_path: str, source_position: str | None = None
) -> dict[str, Any]:
    """Rotate gates in the physical order 乾坎艮震巽離坤兌, never 1..9."""
    if type(anchor) is not int or anchor not in PALACES or duty_gate not in DOORS:
        raise ValueError("太乙门盘需要实际宫位和已知直门")
    else:
        pass
    if anchor == 5:
        return {
            "status": "not_assessed",
            "anchor_number": 5,
            "anchor_palace": "中",
            "anchor_source_path": anchor_path,
            "anchor_source_value": 5,
            "reason": "中五无八方环位，不自动寄坤布门。",
        }
    else:
        pass
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
    else:
        pass
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
                "obstructs": door in GOOD,
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
        "source": TONGZONG,
    }
