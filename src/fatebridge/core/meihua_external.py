"""Selected reported external manifestations, separate from inner cast facts."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/external-manifestations-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_external_manifestations_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected external manifestation profile")
    return profile


def external_manifestation_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _reading(
    body: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    fact_prefix: str,
    interpretation_prefix: str,
) -> dict[str, Any]:
    profile = _profile()
    rows = []
    parts = []
    for index, observation in enumerate(observations):
        kind = observation["manifestation"]
        category = profile["manifestations"].get(kind)
        if category is None:
            from .meihua_omen_reversal import additional_manifestation

            category = additional_manifestation(kind)
        raw = relationship_by_role(body["element"], category["element"])
        rule = next(
            (
                rule
                for rule in profile["rules"]
                if rule["manifestation"] == kind
                and rule["body_element"] == body["element"]
            ),
            None,
        )
        text = (
            rule["reading"]
            if rule is not None
            else (
                "旧实物资格条款未覆盖本配对；本段仅列符号生克，《内外论》的原体象义限定另列"
                if "mapping_ruleset_id" in category
                else "所选条款未覆盖这一原体与外应类别配对；保留符号生克，不补成已有作用或吉凶"
            )
        )
        rows.append(
            {
                "record_index": index,
                **(
                    {"mapping_ruleset_id": category["mapping_ruleset_id"]}
                    if "mapping_ruleset_id" in category
                    else {}
                ),
                "manifestation": kind,
                "reported_fact_path": f"{interpretation_prefix}.external_omens.reported_observations.{index}",
                "body": body["name"],
                "body_element": body["element"],
                "body_fact_path": fact_prefix + ".body_trigram",
                "external_element": category["element"],
                "raw_relation_to_body": raw,
                "qualification": (
                    rule["qualification"]
                    if rule is not None
                    else "not_addressed_in_selected_pairs"
                ),
                "rule_id": rule["id"] if rule is not None else None,
                "quote": rule["quote"] if rule is not None else None,
                "original_pdf_index": rule["pdf_index"] if rule is not None else None,
                "quote_original_pdf_indices": (
                    deepcopy(rule["quote_original_pdf_indices"])
                    if rule is not None
                    else []
                ),
                "reading": text,
                "unique_external_trigram_assigned": False,
                "physical_causation_verified": False,
                "numeric_effect_strength": None,
                "real_outcome": None,
            }
        )
        parts.append(
            f"外应记录{index + 1}按所报{category['description']}，"
            f"类别五行为{category['element']}，对原体{body['name']}的符号关系为{raw}；{text}。"
        )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": external_manifestation_ruleset(),
        "declaration_status": "caller_reported_unverified",
        "reported_observations": deepcopy(observations),
        "reference_body": "original_static_body_of_this_candidate",
        "observations": rows,
        "event_time": None,
        "combined_outcome": None,
        "internal_external_synthesis": "not_computed",
        "independent_verified_observations": 0,
        "summary": "".join(parts)
        + "上述是所选传统条款对已报类别的资格区分，未与内卦合成为现实结果或日期。",
    }


def apply_external_omens(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    observations: list[dict[str, Any]] | None,
) -> None:
    """Enrich completed main/candidate readings; never draw or modify the cast."""
    interpretation["external_omens"] = None
    if observations is None:
        return
    selected = _reading(
        cast["body_trigram"],
        observations,
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
    )
    interpretation["external_omens"] = selected
    suffix = selected["summary"]
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        layer = _reading(
            cast["counting_variants"][index]["body_trigram"],
            observations,
            fact_prefix=f"meihua.counting_variants.{index}",
            interpretation_prefix=f"interpretation.casting_readings.{index}",
        )
        row["external_omens"] = layer
        label = "原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径"
        suffix += label + "外应另核：" + layer["summary"]
    interpretation["comprehensive_judgement"] += suffix
    if interpretation.get("traditional_judgement"):
        interpretation["traditional_judgement"] += selected["summary"]
    interpretation["evidence_scope"][
        "external_omens"
    ] = "caller_reported_selected_manifestation_pairs"
    interpretation["evidence_scope"][
        "external_qualification_scope"
    ] = "No scene verification, unique trigram assumption, net outcome, physical/clinical/hazard assessment or event date"
    cast["evidence_scope"]["implemented"].append(
        "selected_external_manifestation_pairs"
    )
    cast["evidence_scope"]["not_implemented"] = [
        (
            "full_external_omens_synthesis"
            if item in {"external_omens", "external_omens_interpretation"}
            else item
        )
        for item in cast["evidence_scope"]["not_implemented"]
    ]
    from .meihua_omen_reversal import apply_omen_reversal

    apply_omen_reversal(cast, interpretation)
