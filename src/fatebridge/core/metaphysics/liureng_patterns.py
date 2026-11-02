"""Derive named subtypes from calculation facts, never from the reference table.

Naming follows 探原's 九宗门 summary, which distinguishes 比用/知一,
自任/自信/杜传/不虞 and 无依/无亲. Its tabular annotations are audited
separately: a matching transmission sequence does not prove a matching name.
"""

from __future__ import annotations

from typing import Any

from .liureng_transmissions import PUNISHMENT
from .ren_evidence import liuren_annotation_note
from .ren_gods import TANYUAN_TRANSCRIPTION


def classify_transmission_pattern(
    *,
    day_ganzhi: str,
    style: str,
    detail: str,
    method: str,
    lessons: list[dict[str, Any]],
    transmissions: list[str],
    selected_lesson: int | None,
) -> dict[str, Any]:
    thieves = [r["index"] for r in lessons if r["upper_lower_relation"] == "下贼上"]
    killers = [r["index"] for r in lessons if r["upper_lower_relation"] == "上克下"]
    initial, middle, final = transmissions
    yang = day_ganzhi[0] in "甲丙戊庚壬"
    initial_self = PUNISHMENT[initial] == initial
    closing_punishment = PUNISHMENT[middle] in (initial, middle)
    final_detail = detail
    final_method = method

    def direct_label() -> str:
        if detail in ("重审", "元首"):
            return (
                "始入"
                if len(thieves) == 1 and not killers
                else "重审" if thieves else "元首"
            )
        if detail == "知一":
            return "比用" if thieves else "知一"
        return "缀瑕" if detail == "复等" else detail

    if style == "伏吟":
        if day_ganzhi[0] == "癸":
            labels = ["不虞", "元首"]
        elif initial_self or closing_punishment:
            labels = ["杜传"] + (["始入"] if day_ganzhi[0] == "乙" else [])
        else:
            labels = ["自任" if yang else "自信"]
        final_detail = labels[0]
        reason = (
            f"伏吟初{initial}、中{middle}、末{final}；"
            f"初传自刑{'是' if initial_self else '否'}，"
            f"中传之刑回到初中传{'是' if closing_punishment else '否'}。"
        )
    elif style == "返吟":
        if thieves or killers:
            subordinate = direct_label()
            labels = ["无依", subordinate]
            final_detail = detail if detail == "复等" else subordinate
            reason = f"返吟仍有贼克：下贼上课{thieves}、上克下课{killers}，按{subordinate}取初传{initial}。"
        else:
            secondary = (
                "八专" if day_ganzhi in ("甲寅", "庚申", "丁未", "己未") else "井栏射"
            )
            labels = ["无亲", secondary]
            final_detail, final_method = "无亲", "返吟无亲"
            reason = (
                f"返吟四课无贼克，初传{initial}从日支驿马派生，不标记某一课被选中。"
            )
    elif style in ("重审", "元首", "比用", "涉害"):
        labels = [direct_label()]
        final_detail = detail if detail == "复等" else labels[0]
        if style == "比用":
            final_method = labels[0]
        reason = f"下贼上课{thieves}、上克下课{killers}，实际选第{selected_lesson}课{initial}发用，细分为{labels[0]}。"
    elif style == "八专":
        labels = ["八专"] + (["独足"] if len(set(transmissions)) == 1 else [])
        final_detail = "独足" if len(labels) == 2 else "八专"
        reason = f"八专派生三传{initial}{middle}{final}，三传同支{'是' if len(set(transmissions)) == 1 else '否'}。"
    else:
        labels = [detail]
        reason = f"按{style}{detail}派生三传{initial}{middle}{final}。"
    # Append source disagreement after deriving the labels. It cannot affect
    # the selected lesson, transmissions, or computed classification.
    note = liuren_annotation_note(day_ganzhi, lessons[0]["upper_branch"])
    if note:
        reason += f" 影印表注{note['annotation']}；{note['explanation']}"
    return {
        "ruleset_id": "tanyuan_jiuzong_names_v1",
        "source_url": TANYUAN_TRANSCRIPTION,
        "source_section": "推演篇·三传 / 九宗门总说",
        "labels": labels,
        "detail": final_detail,
        "transmission_method": final_method,
        "lower_thief_lessons": thieves,
        "upper_killer_lessons": killers,
        "initial_self_punishment": initial_self if style == "伏吟" else None,
        "closing_punishment": closing_punishment if style == "伏吟" else None,
        "selected_lesson": selected_lesson,
        "basis": reason,
        "source_note": note,
        "scope": "按计算事实推导细课名；表内逐课注名和正文异文另行核验，不据课名断现实事件",
    }
