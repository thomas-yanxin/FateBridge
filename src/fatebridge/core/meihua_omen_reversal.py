"""Preserve common omen symbols and two explicit original-body negations.

不凶 is never promoted to 吉 or physical safety. These symbolic cases do not
replace material qualifications or establish a complete internal/external result.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role

NEW_MANIFESTATIONS = ("gold_silver_treasure", "weapon")


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/omen-reversal-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if value["id"] != "meihua_omen_reversal_nlc1925_v1" or value["version"] != "1.0.0":
        raise ValueError("Unknown selected omen-reversal profile")
    return value


def additional_manifestation(kind: str) -> dict[str, Any]:
    """Explicit new source category; never extend the old material rule pairs."""
    profile = _profile()
    if kind not in profile["manifestations"]:
        raise ValueError("Unknown external manifestation category")
    return {
        **deepcopy(profile["manifestations"][kind]),
        "mapping_ruleset_id": profile["id"],
    }


def _reading(
    body: dict[str, Any],
    external: dict[str, Any],
    *,
    external_path: str,
    body_path: str,
) -> dict[str, Any] | None:
    profile = _profile()
    if profile["body_elements"].get(body["name"]) != body["element"]:
        raise ValueError("Original body trigram and element disagree")
    records = []
    summaries = []
    observations = external["reported_observations"]
    if len(observations) != len(external["observations"]):
        raise ValueError("External observations and computed rows must remain bound")
    for index, observation in enumerate(observations):
        kind = observation["manifestation"]
        if kind not in profile["cases"]:
            continue
        computed = external["observations"][index]
        actual = relationship_by_role(body["element"], "金")
        if (
            computed["record_index"],
            computed["manifestation"],
            computed["body_fact_path"],
            computed["body"],
            computed["body_element"],
            computed["external_element"],
            computed["raw_relation_to_body"],
        ) != (index, kind, body_path, body["name"], body["element"], "金", actual):
            raise ValueError(
                "Omen qualification must use this candidate's actual body and relation"
            )
        rule = profile["cases"][kind]
        matched = body["name"] in rule["qualified_bodies"]
        qualified = rule["qualified_symbol"] if matched else None
        records.append(
            {
                "record_index": index,
                "manifestation": kind,
                "reported_fact_path": f"{external_path}.reported_observations.{index}.manifestation",
                "original_body": {
                    "trigram": body["name"],
                    "element": body["element"],
                    "fact_path": computed["body_fact_path"],
                },
                "raw_relation_to_body": actual,
                "relation_fact_path": f"{external_path}.observations.{index}.raw_relation_to_body",
                "common_source_symbol": rule["common_symbol"],
                "selected_body_condition": {
                    "named_trigrams": deepcopy(rule["qualified_bodies"]),
                    "matches_actual_body": matched,
                },
                "qualified_source_symbol": qualified,
                "qualification_status": (
                    "selected_body_condition_matched"
                    if matched
                    else "body_outside_two_selected_examples"
                ),
                "quote": rule["quote"],
                "original_pdf_index": profile["source"]["original_pdf_index"],
                "material_qualification": computed["qualification"],
                "material_qualification_fact_path": f"{external_path}.observations.{index}.qualification",
                "real_outcome": None,
            }
        )
        label = "金银世宝" if kind == "gold_silver_treasure" else "兵刃"
        if matched:
            wording = "反为不吉" if kind == "gold_silver_treasure" else "反为不凶"
            summaries.append(
                f"所报{label}的通常象义须核原体；本候选为{body['name']}体，所选《内外论》作‘{wording}’，不把否定词改写成相反的确定吉凶。"
            )
        else:
            summaries.append(
                f"所报{label}对原体{body['name']}为{actual}；该原体不属所选两则明示例，通常吉凶象不据此直接成为本例结论。"
            )
    if not records:
        return None
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": deepcopy(profile),
        "scope": "two_selected_body_qualified_symbol_cases_not_full_internal_external_judgement",
        "records": records,
        "source_negations_preserved": True,
        "not_inauspicious_promoted_to_auspicious": False,
        "material_qualification_overridden": False,
        "independent_verified_observations": 0,
        "full_internal_external_synthesis": None,
        "real_outcome": None,
        "event_time": None,
        "success_probability": None,
        "summary": "".join(summaries)
        + "这只是原体限定的传统象义，不替换实物资格，不合成为现实结果、物品安全保证或应期。",
    }


def apply_omen_reversal(cast: dict[str, Any], interpretation: dict[str, Any]) -> None:
    """Qualify each actual candidate separately, leaving every old material row."""
    external = interpretation.get("external_omens")
    if external is None:
        return
    if not any(
        o["manifestation"] in NEW_MANIFESTATIONS
        for o in external["reported_observations"]
    ):
        return
    layer = _reading(
        cast["body_trigram"],
        external,
        external_path="interpretation.external_omens",
        body_path="meihua.body_trigram",
    )
    if layer is None:
        return
    external["body_relative_symbols"] = layer
    external["summary"] += layer["summary"]
    suffix = layer["summary"]
    for index, reading in enumerate(interpretation.get("casting_readings") or []):
        own = reading["external_omens"]
        candidate = _reading(
            cast["counting_variants"][index]["body_trigram"],
            own,
            external_path=f"interpretation.casting_readings.{index}.external_omens",
            body_path=f"meihua.counting_variants.{index}.body_trigram",
        )
        if candidate is None:
            raise ValueError(
                "Each actual candidate must retain the same declared categories"
            )
        own["body_relative_symbols"] = candidate
        own["summary"] += candidate["summary"]
        suffix += (
            ("原数口径" if reading["line_sum_basis"] == "raw_counts" else "卦序数口径")
            + "宝象与凶器另核："
            + candidate["summary"]
        )
    interpretation["comprehensive_judgement"] += suffix
    if interpretation.get("traditional_judgement"):
        interpretation["traditional_judgement"] += layer["summary"]
