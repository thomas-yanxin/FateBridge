"""Explicit chapter subjects and unquantified 多, without occurrence votes."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROLE = {"travel": "body", "traveler": "use"}
_NAMES = {"乾", "兑", "离", "震", "巽", "坎", "艮", "坤"}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    result: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/qualified-chapter-motion-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        result["id"] != "meihua_qualified_chapter_motion_nlc1925_v1"
        or result["version"] != "1.0.0"
        or len(result["rows"]) != 4
        or len({r["id"] for r in result["rows"]}) != 4
        or any(
            r["role"] != _ROLE.get(r["topic"])
            or r["role_key"] != r["role"] + "_trigram"
            for r in result["rows"]
        )
        or any("多" not in r["qualified_predicate"] for r in result["rows"])
    ):
        raise ValueError("Unknown or incomplete qualified chapter-motion reading")
    return result


def build_qualified_motion(
    cast: dict[str, Any], topic: str, *, fact_prefix: str
) -> dict[str, Any]:
    """Select a singular original role; full source/outcome predicates stay open."""
    if topic not in _ROLE:
        raise ValueError("Select travel or traveler for the qualified chapter reading")
    profile = _profile()
    role = _ROLE[topic]
    name = cast[role + "_trigram"]["name"]
    if name not in _NAMES:
        raise ValueError("Qualified chapter reading requires a known original trigram")
    path = fact_prefix + "." + role + "_trigram.name"
    clauses = [
        {
            **deepcopy(row),
            "selected_role": role,
            "selected_trigram": name,
            "trigram_fact_path": path,
            "category_matches": name in row["trigrams"],
            "full_clause_condition": None,
            "numeric_frequency": None,
            "occurrence_count_used": False,
            "verified_real_state": None,
        }
        for row in profile["rows"]
        if row["topic"] == topic
    ]
    matches = [row for row in clauses if row["category_matches"]]
    if len(clauses) != 2 or len(matches) > 1:
        raise ValueError("Qualified chapter categories must be disjoint")
    label = "初体" if role == "body" else "初用"
    values = {"role_label": label, "trigram": name}
    if matches:
        values.update(
            quote=matches[0]["quote"],
            qualified_predicate=matches[0]["qualified_predicate"],
        )
    summary = profile["summary_templates"][
        "matched" if matches else "not_matched"
    ].format(**values)
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "topic": topic,
        "source": deepcopy(profile["source"]),
        "lexical_reference": deepcopy(profile["lexical_reference"]),
        "reading_status": profile["reading_status"],
        "reading_punctuation_is_editorial": True,
        "selected_role": role,
        "selected_trigram": name,
        "trigram_fact_path": path,
        "clauses": clauses,
        "matched_clause_ids": [row["id"] for row in matches],
        "qualified_predicates": [row["qualified_predicate"] for row in matches],
        "status": "category_matched" if matches else "no_selected_category_clause",
        "motion_axis": "chapter_trigram_category_qualified_symbol",
        "inner_role_motion_comparison": deepcopy(profile["inner_role_comparison"]),
        "inner_role_motion_overridden": False,
        "external_observation_inferred": False,
        "occurrence_counts_enter_condition": False,
        "alternative_count_interpretations_adjudicated": False,
        "full_chapter_synthesis": None,
        "unique_all_school_reading_established": False,
        "independent_human_expert_review": False,
        "event_time": None,
        "real_location": None,
        "real_state": None,
        "travel_instruction": None,
        "hazard_verdict": None,
        "success_probability": None,
        "real_outcome": None,
        "predictive_efficacy_established": False,
        "summary": summary,
    }
