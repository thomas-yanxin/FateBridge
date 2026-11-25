"""Fixed eight-palace sand/water preferences over confirmed observations."""

from typing import Any

from fatebridge.core.fengshui.directions import rule_data
from fatebridge.core.fengshui.models import JinsuoRequest


def jinsuo(req: JinsuoRequest) -> dict[str, Any]:
    preferences = {
        d: {
            **i,
            "preferred_classification": (
                "sand" if i["palace_number"] in {1, 2, 3, 4} else "water"
            ),
            "rule_id": "jinsuo_basic_fixed_v1.palace_preference",
            "source_ids": ["S5"],
        }
        for d, i in rule_data("directions").items()
    }
    missing = [] if req.features else ["confirmed_environment_features"]
    findings = []
    for feature in req.features:
        known = feature.classification in {"sand", "water"}
        if not known:
            missing.append(
                f"features.{feature.object_id}.single_confirmed_classification"
            )
        else:
            pass
        preference = preferences[feature.direction]["preferred_classification"]
        findings.append(
            {
                **feature.model_dump(),
                "method": "jinsuo",
                "subject_id": "environment",
                "purpose": "basic_sand_water",
                "preferred_classification": preference,
                "finding": (
                    (
                        "matches_preference"
                        if feature.classification == preference
                        else "opposes_preference"
                    )
                    if known
                    else "undetermined"
                ),
                "rule_id": "jinsuo_basic_fixed_v1.palace_preference",
                "source_ids": ["S5"],
            }
        )
    return {
        "status": "partial" if missing else "complete",
        "preferences": preferences,
        "feature_findings": findings,
        "missing_inputs": missing,
        "coverage_scope": "supplied_features_only_not_complete_environment_survey",
    }
