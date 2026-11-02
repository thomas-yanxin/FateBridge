"""Selected NLC1925 topic clauses from each actual original body/use pair."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .meihua import meihua_stage_relations, meihua_traditional_readings
from .meihua_countercontrol import build_internal_countercontrol
from .meihua_dining import DINING_TOPIC, dining_qualifications, dining_ruleset
from .meihua_general_variants import build_general_casting_readings
from .meihua_households import (
    HOUSEHOLD_TOPICS,
    household_qualifications,
    household_ruleset,
)
from .meihua_journeys import JOURNEY_TOPICS, journey_ruleset, travel_qualifications
from .meihua_lost_property import (
    LOST_PROPERTY_TOPIC,
    lost_property_qualifications,
    lost_property_ruleset,
)
from .meihua_marriage import MARRIAGE_TOPIC, marriage_qualifications, marriage_ruleset
from .meihua_seasonal_reading import build_seasonal_qualification
from .meihua_text_reference import render_yaoci_text
from .meihua_traveler import TRAVELER_TOPIC, traveler_qualifications, traveler_ruleset
from .meihua_wealth import build_wealth_components
from .zhouyi import classical_hexagram

TOPICS = ("planning", "reputation", "wealth", "transaction")
RELATIONS = ("体克用", "用克体", "体生用", "用生体", "体用比和")


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/topics-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_topic_clauses_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected Meihua topic profile")
    if len(profile["rules"]) != 20 or {
        (r["topic"], r["relation"]) for r in profile["rules"]
    } != {(t, r) for t in TOPICS for r in RELATIONS}:
        raise ValueError("Each selected topic must retain all five relation clauses")
    return profile


def topic_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _selected_profile(topic: str) -> dict[str, Any]:
    if topic == DINING_TOPIC:
        return dining_ruleset()
    if topic == MARRIAGE_TOPIC:
        return marriage_ruleset()
    if topic in HOUSEHOLD_TOPICS:
        return household_ruleset()
    if topic == TRAVELER_TOPIC:
        return traveler_ruleset()
    if topic == LOST_PROPERTY_TOPIC:
        return lost_property_ruleset()
    return journey_ruleset() if topic in JOURNEY_TOPICS else topic_ruleset()


def _clause(cast: dict[str, Any], topic: str, *, fact_prefix: str) -> dict[str, Any]:
    profile = _selected_profile(topic)
    chapter = profile["topics"][topic]
    stages = meihua_stage_relations(cast, fact_prefix=fact_prefix)
    initial = next(row for row in stages if row["role"] == "use")
    rule = next(
        r
        for r in profile["rules"]
        if r["topic"] == topic and r["relation"] == initial["relation"]
    )
    result = {
        "topic": topic,
        "label": chapter["label"],
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "selected_edition_id": profile["selected_edition_id"],
        "source": deepcopy(profile["source"]),
        "section": chapter["section"],
        "body_role": "主",
        "use_role": chapter["use_role"],
        "body": initial["body"],
        "use": initial["trigram"],
        "relation": initial["relation"],
        "body_fact_path": fact_prefix + ".body_trigram",
        "use_fact_path": fact_prefix + ".use_trigram",
        "relation_fact_path": fact_prefix + ".stage_relations.0.relation",
        "clause_id": rule["id"],
        "quote": rule["quote"],
        "reading": rule["reading"],
        "semantic_tags": deepcopy(rule["semantic_tags"]),
        "delay_scope": rule["delay_scope"],
        "source_witness": deepcopy(rule["source_witness"]),
        "comparison_reading": {
            **deepcopy(rule["comparison_reading"]),
            "source": deepcopy(profile["comparison_source"]),
            "used_to_override_selected_edition": False,
        },
        "selection_scope": "original_static_body_vs_original_moving_use_only",
        "full_stage_strength_synthesis": "not_computed",
        "event_time": None,
        "success_probability": None,
        "real_outcome_verdict": None,
    }
    if topic in HOUSEHOLD_TOPICS:
        result["source_relation_condition"] = rule["source_relation_condition"]
        result["source_relation_selection_status"] = rule["selection_status"]
        result["chapter_qualifications"] = household_qualifications(
            cast, topic, fact_prefix=fact_prefix
        )
    return result


def _summary(clause: dict[str, Any]) -> str:
    return (
        f"按所选文明书局本《{clause['section']}》，原体{clause['body']}、用{clause['use']}为{clause['relation']}；"
        f"原文作“{clause['quote']}”。{clause['reading']}。"
        + (
            clause["chapter_qualifications"]["summary"]
            if "chapter_qualifications" in clause
            else ""
        )
    )


def build_topic_interpretation(cast: dict[str, Any], topic: str) -> dict[str, Any]:
    """Keep chapter, edition and each count candidate's actual relation separate."""
    if topic not in (
        *TOPICS,
        *JOURNEY_TOPICS,
        LOST_PROPERTY_TOPIC,
        TRAVELER_TOPIC,
        *HOUSEHOLD_TOPICS,
        MARRIAGE_TOPIC,
        DINING_TOPIC,
    ):
        raise ValueError("Select one of the published Meihua topic chapters")
    selected = _clause(cast, topic, fact_prefix="meihua")
    stages = meihua_stage_relations(cast)
    seasonal = cast.get("seasonal_strength")
    control = build_internal_countercontrol(stages)
    strength_reading = build_seasonal_qualification(stages, seasonal, control)
    stage_readings, _ = meihua_traditional_readings(
        stages,
        seasonal,
        internal_countercontrol=control,
        seasonal_qualification=strength_reading,
    )
    branch = seasonal["month_branch"] if seasonal is not None else None
    alternatives = build_general_casting_readings(cast, branch)
    if topic == DINING_TOPIC:
        selected["chapter_qualifications"] = dining_qualifications(
            cast,
            stages,
            control,
            fact_prefix="meihua",
            interpretation_prefix="interpretation",
        )
    if topic == MARRIAGE_TOPIC:
        selected["chapter_qualifications"] = marriage_qualifications(
            cast,
            stages,
            seasonal,
            fact_prefix="meihua",
            strength_prefix="meihua.seasonal_strength",
        )
    if topic == "travel":
        selected["chapter_qualifications"] = travel_qualifications(
            cast,
            stages,
            seasonal,
            fact_prefix="meihua",
            strength_prefix="meihua.seasonal_strength",
            interpretation_prefix="interpretation",
        )
    if topic == LOST_PROPERTY_TOPIC:
        selected["chapter_qualifications"] = lost_property_qualifications(
            cast, stages, fact_prefix="meihua"
        )
    if topic == TRAVELER_TOPIC:
        selected["chapter_qualifications"] = traveler_qualifications(
            cast,
            stages,
            seasonal,
            fact_prefix="meihua",
            strength_prefix="meihua.seasonal_strength",
        )
    wealth = (
        build_wealth_components(stages, seasonal, control)
        if topic == "wealth"
        else None
    )
    for index, row in enumerate(alternatives["casting_readings"]):
        row["topic_clause"] = _clause(
            cast["counting_variants"][index],
            topic,
            fact_prefix=f"meihua.counting_variants.{index}",
        )
        if topic == DINING_TOPIC:
            row["topic_clause"]["chapter_qualifications"] = dining_qualifications(
                cast["counting_variants"][index],
                row["stage_relations"],
                row["internal_countercontrol"],
                fact_prefix=f"meihua.counting_variants.{index}",
                interpretation_prefix=f"interpretation.casting_readings.{index}",
            )
        if topic == MARRIAGE_TOPIC:
            row["topic_clause"]["chapter_qualifications"] = marriage_qualifications(
                cast["counting_variants"][index],
                row["stage_relations"],
                row["seasonal_strength"],
                fact_prefix=f"meihua.counting_variants.{index}",
                strength_prefix=f"interpretation.casting_readings.{index}.seasonal_strength",
            )
        if topic == "travel":
            row["topic_clause"]["chapter_qualifications"] = travel_qualifications(
                cast["counting_variants"][index],
                row["stage_relations"],
                row["seasonal_strength"],
                fact_prefix=f"meihua.counting_variants.{index}",
                strength_prefix=f"interpretation.casting_readings.{index}.seasonal_strength",
                interpretation_prefix=f"interpretation.casting_readings.{index}",
            )
        if topic == "wealth":
            row["wealth_components"] = build_wealth_components(
                row["stage_relations"],
                row["seasonal_strength"],
                row["internal_countercontrol"],
                fact_prefix=f"meihua.counting_variants.{index}",
                interpretation_prefix=f"interpretation.casting_readings.{index}",
            )
        if topic == LOST_PROPERTY_TOPIC:
            row["topic_clause"]["chapter_qualifications"] = (
                lost_property_qualifications(
                    cast["counting_variants"][index],
                    row["stage_relations"],
                    fact_prefix=f"meihua.counting_variants.{index}",
                )
            )
        if topic == TRAVELER_TOPIC:
            row["topic_clause"]["chapter_qualifications"] = traveler_qualifications(
                cast["counting_variants"][index],
                row["stage_relations"],
                row["seasonal_strength"],
                fact_prefix=f"meihua.counting_variants.{index}",
                strength_prefix=f"interpretation.casting_readings.{index}.seasonal_strength",
            )
    for row in alternatives["casting_readings"]:
        # The explicitly chosen chapter owns this candidate's initial judgement.
        # General-stage context remains available in its separate source fields.
        row["traditional_judgement"] = (
            _summary(row["topic_clause"])
            + row["internal_countercontrol"]["summary"]
            + row["seasonal_qualification"]["summary"]
            + (row["wealth_components"]["summary"] if topic == "wealth" else "")
        )
    clauses = [row["topic_clause"] for row in alternatives["casting_readings"]]
    alternatives["casting_comparison"].update(
        changed_topic_clause_ids=(
            sorted({c["clause_id"] for c in clauses})
            if len({c["clause_id"] for c in clauses}) > 1
            else []
        ),
        same_initial_clause_does_not_imply_same_stage_context=True,
        topic_clause_scope="each_candidate_own_original_body_use_not_selected_cast_copy",
    )
    if topic == LOST_PROPERTY_TOPIC:
        locations = {c["chapter_qualifications"]["selected_trigram"] for c in clauses}
        alternatives["casting_comparison"].update(
            changed_lost_location_trigrams=(
                sorted(locations) if len(locations) > 1 else []
            ),
            single_real_location=None,
            location_candidates_used_as_outcome_votes=False,
        )
    reference = classical_hexagram(cast["base_hexagram"]["binary_code"])
    line = cast["seed"]["moving_line"]
    verse = next(v for v in reference["yaoci"] if v["position"] == line)
    summary = _summary(selected) + control["summary"] + strength_reading["summary"]
    if wealth is not None:
        summary += wealth["summary"]
    if clauses:
        summary += " 各取数候选另列：" + "".join(
            ("原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径")
            + ("（本次所选）" if row["selected"] else "")
            + f"动{row['moving_line']}爻，"
            + _summary(row["topic_clause"])
            + row["internal_countercontrol"]["summary"]
            + row["seasonal_qualification"]["summary"]
            + (row["wealth_components"]["summary"] if topic == "wealth" else "")
            for row in alternatives["casting_readings"]
        )
    summary += (
        " 以上为所选版本的初始体用条款及已列求财补充依据；互变与旺衰另列，尚未综合为现实成败、收益概率或具体应期。"
        if wealth is not None
        else " 以上为所选版本的初始体用条款；互变与旺衰另列，尚未综合为现实成败、收益概率或具体应期。"
    )
    return {
        "interpretation_topic": topic,
        "weather": None,
        "question_domain": {
            "key": topic,
            "label": selected["label"],
            "focus": "所选题篇及实际原体用关系",
        },
        "topic_reading": selected,
        "topic_ruleset": _selected_profile(topic),
        "wealth_components": wealth,
        "internal_countercontrol": control,
        "seasonal_qualification": strength_reading,
        "traditional_stage_readings": stage_readings,
        "traditional_judgement": _summary(selected)
        + control["summary"]
        + strength_reading["summary"]
        + (wealth["summary"] if wealth is not None else ""),
        "classical_text_reference": {
            "moving_yaoci": verse,
            "moving_yaoci_rendering": render_yaoci_text(verse["text"]),
            "source_url": reference["source_url"],
            "selection_policy": "actual_moving_line_reference_only",
            "scope": "周易经文为独立参照，未据此替换所选题篇的条款或核定现实结果。",
        },
        "action_hint": None,
        "risk_hint": None,
        **alternatives,
        "evidence_scope": {
            "traditional_rules": "interpretation.topic_ruleset",
            "selected_source_edition": "nlc_1925",
            "selected_clause_path": "interpretation.topic_reading",
            "source_character_reading": "assistant selected-span visual reading; no independent human expert authentication",
            "question_keywords_select_chapter": False,
            "initial_clause_applied_automatically_to_all_stages": False,
            "relative_delay_is_numeric_event_time": False,
            "full_themed_chapter_conformance_established": False,
            "chapter_stage_strength_synthesis": "not_computed",
            "wealth_supplement": (
                "interpretation.wealth_components: selected supplement relation atoms; junction and full effect not adjudicated"
                if topic == "wealth"
                else "not_applicable_to_selected_topic"
            ),
            "counting_candidate_readings": "各候选按自己的原体、用和同一已报节月匹配所选章句，不借用主候选结论。",
            "external_omens": "not_collected",
            "event_timing": "not_computed",
            "real_world_efficacy": "not_established",
            "not_implemented": [
                "full_themed_chapter_synthesis",
                (
                    "exact_event_time_or_physical_location"
                    if topic == LOST_PROPERTY_TOPIC
                    else "exact_timing_or_direction"
                ),
                "observed_predictive_validation",
            ],
        },
        "comprehensive_judgement": summary,
    }
