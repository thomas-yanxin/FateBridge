"""Selected declared subjects and compass sides for NLC1925 duanfa casting."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/observed-categories-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_observed_categories_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected observed category profile")
    return profile


def observed_category_profile() -> dict[str, Any]:
    return deepcopy(_profile())


def resolve_reported_observation(
    parameters: dict[str, Any],
) -> tuple[int, int, dict[str, Any]]:
    """Map already validated declared fields; never classify their free text."""
    profile = _profile()
    subject = profile["subjects"][parameters["subject_category"]]
    direction = profile["directions"][parameters["direction"]]
    role = parameters["direction_role"]
    role_label = {"from": "從", "toward": "往", "at": "在"}[role]
    prefix = "meihua.seed.parameters."
    basis = {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "declaration_status": "caller_reported_unverified",
        "subject": {
            "category": parameters["subject_category"],
            "source_label": subject["label"],
            "trigram": subject["trigram"],
            "number": subject["number"],
            "quote": subject["quote"],
            "original_pdf_indices": [subject["pdf_index"]],
            "category_fact_path": prefix + "subject_category",
            "description_fact_path": prefix + "subject_description",
        },
        "direction": {
            "value": parameters["direction"],
            "role": role,
            "trigram": direction["trigram"],
            "number": direction["number"],
            "original_pdf_indices": [direction["pdf_index"]],
            "value_fact_path": prefix + "direction",
            "role_fact_path": prefix + "direction_role",
            "opposite_direction_substituted": False,
            "scope": "declared_eight_direction_label_not_measured_bearing_or_travel_heading",
        },
        "single_subject_fact_path": prefix + "single_subject_confirmed",
        "hour_fact_path": prefix + "hour_branch",
        "scene_verified": False,
        "compass_verified": False,
        "casting_trigger_adjudicated": False,
        "independent_verified_observations": 0,
        "alternative_observation_methods_adjudicated": False,
        "event_time": None,
        "real_outcome": None,
        "summary": (
            f"端法依所報{subject['label']}、{role_label}{direction['label']}方，"
            f"按所選原例及方位圖取上{subject['trigram']}、下{direction['trigram']}。"
            "取爻用先天卦序加所報時支數，未把來方反換成行進方向。"
            "所報類別、單一對象與方位未獨立核實，完整起占條件及其他取法尚未裁定。"
        ),
    }
    return subject["number"], direction["number"], basis
