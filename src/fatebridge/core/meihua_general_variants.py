"""General readings from each retained cast, without choosing a classical winner."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .meihua import meihua_seasonal_strength, meihua_traditional_readings
from .meihua_countercontrol import build_internal_countercontrol
from .meihua_seasonal_reading import build_seasonal_qualification
from .meihua_text_reference import render_yaoci_text
from .zhouyi import classical_hexagram


def build_general_casting_readings(
    cast: dict[str, Any], month_branch: str | None
) -> dict[str, Any]:
    """Reuse held geometry and relations; no new cast or inferred month."""
    readings = []
    for index, variant in enumerate(cast.get("counting_variants", [])):
        prefix = f"meihua.counting_variants.{index}"
        stages = deepcopy(variant["stage_relations"])
        seasonal = meihua_seasonal_strength(variant, month_branch, fact_prefix=prefix)
        control = build_internal_countercontrol(stages, fact_prefix=prefix)
        strength_reading = build_seasonal_qualification(
            stages,
            seasonal,
            control,
            fact_prefix=prefix,
            strength_prefix=f"interpretation.casting_readings.{index}.seasonal_strength",
        )
        stage_readings, traditional = meihua_traditional_readings(
            stages,
            seasonal,
            internal_countercontrol=control,
            seasonal_qualification=strength_reading,
        )
        chapter = classical_hexagram(variant["base_code"])
        verse = next(
            row for row in chapter["yaoci"] if row["position"] == variant["moving_line"]
        )
        readings.append(
            {
                **{
                    key: variant[key]
                    for key in (
                        "line_sum_basis",
                        "selected",
                        "moving_line",
                        "base_code",
                        "changed_code",
                        "mutual_code",
                        "body",
                        "use",
                        "body_use_relation",
                    )
                },
                "fact_prefix": prefix,
                "stage_relations": stages,
                "seasonal_strength": seasonal,
                "internal_countercontrol": control,
                "seasonal_qualification": strength_reading,
                "traditional_stage_readings": stage_readings,
                "traditional_judgement": traditional,
                "classical_text_reference": {
                    "moving_yaoci": verse,
                    "moving_yaoci_rendering": render_yaoci_text(verse["text"]),
                    "source_url": chapter["source_url"],
                    "base_fact_path": prefix + ".base_hexagram",
                    "moving_line_fact_path": prefix + ".moving_line",
                    "selection_policy": "this_candidate_actual_moving_line_reference_only",
                },
            }
        )
    changed_fields = [
        key
        for key in (
            "moving_line",
            "changed_code",
            "mutual_code",
            "body",
            "use",
            "body_use_relation",
        )
        if len({row[key] for row in readings}) > 1
    ]
    changed_relations = [
        role
        for role in ("use", "body_mutual", "use_mutual", "changed_use")
        if len(
            {
                next(s["relation"] for s in row["stage_relations"] if s["role"] == role)
                for row in readings
            }
        )
        > 1
    ]
    return {
        "casting_readings": readings,
        "casting_comparison": {
            "status": (
                "different_interpretation_facts"
                if changed_fields
                else (
                    "no_counting_variants"
                    if not readings
                    else "same_selected_interpretation_facts"
                )
            ),
            "candidate_count": len(readings),
            "changed_fields": changed_fields,
            "changed_stage_relation_roles": changed_relations,
            "internal_control_edges_differ": len(
                {
                    tuple(
                        (e["controller_role"], e["target_role"])
                        for e in row["internal_countercontrol"]["control_edges"]
                    )
                    for row in readings
                }
            )
            > 1,
            "changed_control_qualification_roles": [
                role
                for role in ("use", "body_mutual", "use_mutual", "changed_use")
                if len(
                    {
                        (q["qualification"], tuple(q["incoming_controller_roles"]))
                        for row in readings
                        for q in row["internal_countercontrol"]["qualifications"]
                        if q["role"] == role
                    }
                )
                > 1
            ],
            "season_context": (
                "same_supplied_month_branch"
                if month_branch is not None
                else "not_supplied"
            ),
            "unique_classical_count_convention_established": False,
            "single_outcome_verdict": None,
            "scope": "逐候选核对所列事实；相同生克或旺衰不等于相同爻辞、唯一古法或现实结论。",
        },
    }


def general_casting_summary(readings: list[dict[str, Any]]) -> str:
    """Keep both interpretations visible when the declared count changes the cast."""
    parts = ["各候选分列，未裁定唯一原法。"]
    for row in readings:
        label = "原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径"
        selected = "（本次所选）" if row["selected"] else ""
        display = row["classical_text_reference"]["moving_yaoci_rendering"][
            "display_text"
        ]
        verse_text = display if display is not None else "〔转录标记未解析，原文另存〕"
        parts.append(
            f"{label}{selected}：动{row['moving_line']}爻，原体{row['body']}、用{row['use']}。"
            f"{row['traditional_judgement']}"
            + ("未给节月，季令待定。" if row["seasonal_strength"] is None else "")
            + f"本候选实际动爻经文参照：{verse_text}"
        )
    parts.append("初中终为传统分析层次，未据此计算现实事件成败或发生日期。")
    return "".join(parts)
