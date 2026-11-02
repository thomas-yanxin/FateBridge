"""Selected lost-property text, with an explicit changed-moving-trigram reading."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

LOST_PROPERTY_TOPIC = "lost_property"


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/lost-property-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_lost_property_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 5
        or {row["relation"] for row in profile["rules"]}
        != {"体克用", "用克体", "体生用", "用生体", "体用比和"}
        or len(profile["location_rules"]) != 8
        or {row["trigram"] for row in profile["location_rules"]}
        != set("乾坤震巽坎离艮兑")
        or profile["location_selection_policy"]["scope"] != "changed_use_trigram"
    ):
        raise ValueError("Unknown or incomplete selected lost-property profile")
    return profile


def lost_property_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def lost_property_qualifications(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    *,
    fact_prefix: str,
) -> dict[str, Any]:
    """Select this candidate's changed moving half; never infer a physical place."""
    profile = _profile()
    line = cast["seed"]["moving_line"] if "seed" in cast else cast["moving_line"]
    position = "lower" if line <= 3 else "upper"
    path = f"{fact_prefix}.changed_hexagram.{position}"
    changed_use = next(row for row in stages if row["role"] == "changed_use")
    trigram = cast["changed_hexagram"][position]["name"]
    if changed_use["fact_path"] != path or changed_use["trigram"] != trigram:
        raise ValueError("Lost-property location must use this candidate's changed use")
    rule = next(row for row in profile["location_rules"] if row["trigram"] == trigram)
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "source": deepcopy(profile["source"]),
        "section": "失物占第十五",
        "header_quote": profile["location_header"],
        "selection_policy": deepcopy(profile["location_selection_policy"]),
        "moving_line": line,
        "moving_line_fact_path": (
            fact_prefix + ".seed.moving_line"
            if "seed" in cast
            else fact_prefix + ".moving_line"
        ),
        "selected_role": "changed_use",
        "selected_trigram": trigram,
        "trigram_fact_path": path + ".name",
        "changed_hexagram_positions": {
            p: {
                "trigram": cast["changed_hexagram"][p]["name"],
                "fact_path": f"{fact_prefix}.changed_hexagram.{p}.name",
                "selected": p == position,
            }
            for p in ("lower", "upper")
        },
        "clause_id": rule["id"],
        "quote": rule["quote"],
        "direction_symbol": rule["direction_symbol"],
        "place_symbols": deepcopy(rule["place_symbols"]),
        "source_witness": deepcopy(rule["source_witness"]),
        "comparison_reading": {
            **deepcopy(rule["comparison_reading"]),
            "source": deepcopy(profile["comparison_source"]),
            "used_to_override_selected_edition": False,
        },
        "physical_reference_origin": None,
        "numeric_bearing": None,
        "geographic_coordinates": None,
        "real_location": None,
        "search_permission": None,
        "loss_or_recovery_verified": None,
        "event_time": None,
        "summary": (
            f"失物方位句按已明示的变用经卦读法，取本候选变用{trigram}，"
            f"对应原文{rule['direction_symbol']}及列示地点类象；"
            "该角色读法未认证为全章唯一解释，方位没有现场参照原点，"
            "未核实物品位置、遗失或寻获，不据类象生成搜索许可或寻获日期。"
        ),
    }
