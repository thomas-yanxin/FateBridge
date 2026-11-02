"""Source-bound 27 x 4 to 12 x 9 table; no invented physical birth foot."""

from __future__ import annotations

import copy
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, cast

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_palace_padas.json"
_ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


@lru_cache(maxsize=1)
def source_bundle() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(SOURCE.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _cells() -> tuple[dict[str, Any], ...]:
    palaces = source_bundle()["palaces"]
    if [p["ordinal"] for p in palaces] != list(range(1, 13)):
        raise ValueError("原典分足表必须保留师子起算的十二宫序")
    counts: Counter[str] = Counter()
    cells = []
    for palace in palaces:
        if sum(s["count"] for s in palace["segments"]) != 9:
            raise ValueError("原典每宫须为九足")
        for segment in palace["segments"]:
            name, amount = segment["mansion"], segment["count"]
            if name == "牛" or type(amount) is not int or not 1 <= amount <= 4:
                raise ValueError("原典分足使用不含牛宿的27宿；每段为1..4足")
            for _ in range(amount):
                counts[name] += 1
                cells.append(
                    {
                        "mansion": name,
                        "pada": counts[name],
                        "palace_ordinal": palace["ordinal"],
                        "palace_name": palace["name"],
                        "ruler_luminary": palace["ruler_luminary"],
                        "locator": palace["locator"],
                    }
                )
    expected_names = set("星张翼轸角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳")
    if set(counts) != expected_names or any(c != 4 for c in counts.values()):
        raise ValueError("原典分足表必须为27宿每宿四足，共108足")
    return tuple(cells)


def validate_textual_pada(pada: Optional[int]) -> None:
    if pada is not None and (type(pada) is not int or not 1 <= pada <= 4):
        raise ValueError("textual_pada仅为原典查表的1..4整数足序；不猜测实际出生足位")


def reference_cell(mansion: str, pada: int) -> dict[str, Any]:
    validate_textual_pada(pada)
    if pada is None:
        raise ValueError("单格查询须明确足序")
    name = mansion.translate(_ALIASES)
    cell = next(
        (c for c in _cells() if c["mansion"] == name and c["pada"] == pada), None
    )
    if cell is None:
        raise ValueError("分足查表只支持原典27宿（牛宫不是牛宿）")
    return dict(cell)


def palace_reference(
    context: dict[str, Any], textual_pada: Optional[int] = None
) -> dict[str, Any]:
    validate_textual_pada(textual_pada)
    bundle = source_bundle()
    primary = context.get("natal_su27")
    names = (
        [primary]
        if primary
        else list(dict.fromkeys(context.get("candidate_su27s", [])))
    )
    complete = (
        primary is not None
        or bool(names)
        and context.get("profile_calculation", {}).get(
            "candidate_set_complete_under_declared_reconstructions"
        )
        is True
    )
    rows = [
        reference_cell(name, p)
        for name in names
        for p in ([textual_pada] if textual_pada is not None else range(1, 5))
    ]
    ordinals = list(dict.fromkeys(r["palace_ordinal"] for r in rows))
    palaces = [
        copy.deepcopy({k: v for k, v in p.items() if k != "segments"})
        for p in bundle["palaces"]
        if p["ordinal"] in ordinals
    ]
    resolved = complete and len(palaces) == 1
    return {
        "ruleset_id": bundle["id"],
        "status": (
            "candidate_set_incomplete"
            if not complete
            else (
                "palace_resolved_from_complete_candidates"
                if resolved and primary is None
                else (
                    "palace_resolved_pada_unspecified"
                    if resolved and textual_pada is None
                    else (
                        "reference_cell_selected"
                        if resolved
                        else "mansion_or_pada_ambiguous"
                    )
                )
            )
        ),
        "basis": "textual_table_lookup_by_calendrical_mansion_names_only",
        "mansion": primary,
        "mansion_candidates": names,
        "textual_pada": textual_pada,
        "candidate_set_complete_within_calendar_profile": complete,
        "selected_palace": palaces[0] if resolved else None,
        "candidate_palaces": palaces,
        "rows": rows,
        "pada_numbering_basis": bundle["pada_numbering_basis"],
        "pada_ordinals_explicit_in_source": bundle["pada_ordinals_explicit_in_source"],
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "locator": bundle["locator"],
        "applied_to_calendar_mansion": False,
        "applied_to_sanjiu": False,
        "applied_to_modern_chart": False,
        "birth_pada_established": False,
        "physical_longitude_status": "not_computed_no_historical_reference_origin",
        "scope": bundle["scope"],
    }


def render_palace_reference(reference: dict[str, Any]) -> str:
    palace = reference["selected_palace"]
    if palace:
        result = f"按已列历日宿名查原典分足表，表内宫名候选只有{palace['name']}，原文主曜为{palace['ruler_literal']}。"
    elif reference["candidate_palaces"]:
        result = (
            "原典分足查表候选宫为"
            + "、".join(p["name"] for p in reference["candidate_palaces"])
            + "；未选唯一宫。"
        )
    else:
        result = "尚无可用宿名查询原典分足表，未选宫名。"
    palaces = {p["ordinal"]: p for p in reference["candidate_palaces"]}
    groups: dict[tuple[str, int], list[int]] = {}
    for row in reference["rows"]:
        groups.setdefault((row["mansion"], row["palace_ordinal"]), []).append(
            row["pada"]
        )
    for (mansion, ordinal), padas in groups.items():
        mapped = palaces[ordinal]
        result += (
            f"{mansion}宿第{'、'.join(str(p) for p in padas)}足对应{mapped['name']}、"
            f"主曜{mapped['ruler_literal']}、{mapped['division']}（{mapped['locator']}）；"
        )
    if reference["textual_pada"] is None:
        result += "未指定查表足序，四足均保留；未从出生钟时补足位。"
    else:
        result += (
            f"所选第{reference['textual_pada']}足是显式查表条件，不是已排得出生足位。"
        )
    if not reference["candidate_set_complete_within_calendar_profile"]:
        result += "当前历日宿候选未保证穷尽，不能因已列候选同宫而确定宫名。"
    result += "该查表结果未确定个人本命宫；宫序、太阳/太阴分均为原典表内分类，不是星图House、昼夜生盘或实测月亮黄经。"
    return result
