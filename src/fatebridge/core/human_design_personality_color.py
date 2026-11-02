"""Source category labels from Personality Color, never observed mental states."""

from typing import Any, cast

from fatebridge.core.human_design_references import (
    reference_data,
)
from fatebridge.core.human_design_references import reference_sha256 as catalogue_sha256

SCOPE = "按人格日地／交点的实际Color及对点一致性读取官方类别名；对点来自同一依赖，不是两份独立证据。类别不评定现实动机、性格或能力；本命资料未评估转移、分心或是否对齐，也不提供决策、临床或预测依据。路径相对于本盘或当前联合快照。"


def _reference() -> dict[str, Any]:
    return reference_data("personality-color-reference.json")


def reference_sha256() -> str:
    return catalogue_sha256("personality-color-reference.json")


def personality_colors(activations: dict[str, Any]) -> dict[str, Any]:
    reference = _reference()
    rows = activations.get("personality", [])
    components = {}
    for kind, pair in (
        ("motivation", ("Sun", "Earth")),
        ("view", ("NorthNode", "SouthNode")),
    ):
        matches = [
            [(i, row) for i, row in enumerate(rows) if row.get("body") == body]
            for body in pair
        ]
        valid = all(
            len(found) == 1
            and type(found[0][1].get("color")) is int
            and 1 <= found[0][1]["color"] <= 6
            for found in matches
        )
        color = matches[0][0][1]["color"] if valid else None
        consistent = valid and matches[1][0][1]["color"] == color
        components[kind] = {
            "status": (
                "computed"
                if consistent
                else (
                    "inconsistent_color_pair"
                    if valid
                    else "missing_or_invalid_color_pair"
                )
            ),
            "side": "personality",
            "primary_body": pair[0],
            "mirror_body": pair[1],
            "color": color if consistent else None,
            "source_term": (
                reference["categories"][kind][cast(int, color) - 1]["source_term"]
                if consistent
                else None
            ),
            "basis": (
                [
                    {
                        "path": f"activations.personality.{found[0][0]}.color",
                        "value": found[0][1]["color"],
                    }
                    for found in matches
                ]
                if valid
                else []
            ),
            "source_url": reference["sources"][kind]["url"],
        }
    return {
        "status": (
            "computed"
            if all(c["status"] == "computed" for c in components.values())
            else "incomplete_or_inconsistent"
        ),
        **components,
        "source_catalog_id": reference["source_catalog_id"],
        "source_catalog_sha256": reference_sha256(),
        "observed_transference": None,
        "observed_distraction": None,
        "observed_alignment": None,
        "observation_status": "not_assessed_from_natal_chart",
        "psychological_measurement_certified": False,
        "scope": SCOPE,
    }


def personality_color_reading(
    value: dict[str, Any], comparison: dict[str, Any] | None = None
) -> str:
    parts = [
        f"{label}Color {value[key]['color']}，来源类别名为{value[key]['source_term']}"
        for key, label in (("motivation", "人格日地"), ("view", "人格交点"))
        if value[key]["status"] == "computed"
    ]
    text = "；".join(parts) + "。" if parts else ""
    if value["status"] != "computed":
        text += "缺少一致Color对点的部分未生成类别。"
    if comparison and comparison.get("personality_colors_changed"):
        same_code = (
            comparison["variable_codes"]["before"]
            == comparison["variable_codes"]["after"]
        )
        text += "本次真／平交点的人格Color分类不同；" + (
            "四箭头编码虽相同，仍须分别保留这些分类。"
            if same_code
            else "分别读取同一口径的类别与箭头。"
        )
    return (
        text
        + "这是来源对数值的传统归类；现实动机、能力及转移／分心状态未由本命计算测量。"
    )
