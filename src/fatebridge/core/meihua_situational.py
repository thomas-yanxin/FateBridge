"""Four reported ten-response contexts; preserve source ambiguity and actual body."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/situational-responses-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        value["id"] != "meihua_situational_responses_nlc1925_v1"
        or value["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected situational-response profile")
    return value


def _reading(
    body: dict[str, Any],
    context: dict[str, Any],
    *,
    body_path: str,
    context_path: str,
) -> dict[str, Any]:
    profile = _profile()
    rows = []
    summaries = []
    for family in ("querent_position", "weather", "setting", "human"):
        supplied = context[family]
        if supplied is None:
            continue
        categories = (
            [supplied["direction"]] if family == "querent_position" else supplied
        )
        for index, category in enumerate(categories):
            candidates = []
            for trigram in profile["tables"][family][category]:
                element = profile["trigram_elements"][trigram]
                relation = relationship_by_role(body["element"], element)
                candidates.append(
                    {
                        "trigram": trigram,
                        "element": element,
                        "raw_relation_to_original_body": relation,
                        "direction_clause_preference": (
                            profile["direction_preferences"][relation]
                            if family == "querent_position"
                            else None
                        ),
                    }
                )
            exact = (
                profile["weather_exact_preferred"].get(category)
                if family == "weather"
                else None
            )
            row = {
                "family": family,
                "section": profile["source_heads"][family],
                "category": category,
                "category_label": profile["category_labels"][category],
                "reported_fact_path": (
                    context_path + ".querent_position.direction"
                    if family == "querent_position"
                    else f"{context_path}.{family}.{index}"
                ),
                "reference_label": (
                    supplied["reference_label"]
                    if family == "querent_position"
                    else None
                ),
                "body": {
                    "trigram": body["name"],
                    "element": body["element"],
                    "fact_path": body_path,
                },
                "trigram_candidates": candidates,
                "candidate_selection": "all_named_source_trigrams_no_unique_choice",
                "source_symbolic_valence": (
                    profile["human_symbolic_valence"].get(category)
                    if family == "human"
                    else None
                ),
                "exact_weather_pair": (
                    {
                        "source_body": exact,
                        "matches_actual_body": body["name"] == exact,
                        "source_weather_condition_status": (
                            "pending_rain_vs_snow"
                            if category == "rain_or_snow"
                            else "reported_literal_condition"
                        ),
                        "clause_applies_to_reported_conditions": (
                            False
                            if body["name"] != exact
                            else None if category == "rain_or_snow" else True
                        ),
                        "quote": profile["weather_exact_quotes"][category],
                    }
                    if exact is not None
                    else None
                ),
                "unresolved_source_relation_clause": (
                    deepcopy(profile["thunder_relation_clause"])
                    if family == "weather" and category == "thunder"
                    else None
                ),
                "combined_effect": None,
                "event_time": None,
                "real_outcome": None,
            }
            rows.append(row)
            detail = "、".join(
                f"{c['trigram']}{c['element']}（{c['raw_relation_to_original_body']}）"
                for c in candidates
            )
            if not detail:
                detail = "原文喜庆象" if category == "heard_laughter" else "原文悲愁象"
            summaries.append(
                f"{row['section']}按已报{row['category_label']}列{detail}。"
            )
    summary = (
        "".join(summaries)
        if rows
        else "所报十应现场资料尚无已确认类别；不把缺项当作确认现场无应。"
    )
    if any(
        r["family"] == "weather" and r["category"] in {"snow", "rain_or_snow"}
        for r in rows
    ):
        summary += "雨雪均取坎象，但原句坎體宜雨只明说雨；已报雪不扩充为宜雪，雨雪未分时宜雨条件待定。"
    if any(r["unresolved_source_relation_clause"] is not None for r in rows):
        summary += "所选影印‘體見雷為比和’的主语接续未裁定，转录‘火見雷’另存，均不覆盖上述五行关系。"
    summary += "这些是同次已报条件的传统对应，未合成为现实结果、概率或应期。"
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": deepcopy(profile),
        "reported_context": deepcopy(context),
        "context_fact_path": context_path,
        "declaration_status": "caller_reported_unverified",
        "status": (
            "reported_categories_mapped" if rows else "pending_reported_categories"
        ),
        "reference_body": "this_candidate_original_static_body",
        "uncollected_families": [
            name for name in profile["source_heads"] if context[name] is None
        ],
        "observations": rows,
        "ten_response_synthesis": None,
        "internal_external_synthesis": None,
        "independent_verified_observations": 0,
        "changes_casting_or_registered_study_eligibility": False,
        "event_time": None,
        "real_outcome": None,
        "success_probability": None,
        "summary": summary,
    }


def apply_situational_responses(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    context: dict[str, Any] | None,
    *,
    context_fact_path: str,
) -> None:
    """Use each retained candidate's own body; never alter or select its cast."""
    if context is None:
        return
    if interpretation["interpretation_topic"] == "weather":
        raise ValueError("十应体用现场条件不能套用天时占")
    layer = _reading(
        cast["body_trigram"],
        context,
        body_path="meihua.body_trigram",
        context_path=context_fact_path,
    )
    interpretation["situational_responses"] = layer
    suffix = layer["summary"]
    for index, reading in enumerate(interpretation.get("casting_readings") or []):
        own = cast["counting_variants"][index]
        row = _reading(
            own["body_trigram"],
            context,
            body_path=f"meihua.counting_variants.{index}.body_trigram",
            context_path=context_fact_path,
        )
        reading["situational_responses"] = row
        suffix += (
            ("原数口径" if reading["line_sum_basis"] == "raw_counts" else "卦序数口径")
            + "十应现场另核："
            + row["summary"]
        )
    interpretation["comprehensive_judgement"] += suffix
    interpretation["evidence_scope"][
        "situational_responses"
    ] = "four_selected_same_cast_reported_context_heads_not_full_synthesis"
