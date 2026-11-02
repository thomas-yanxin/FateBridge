"""Outcome-independent score bounds for complete, already fixed forecasts.

This checks a research endpoint, not the truth of a traditional weather rule.
An abstention earns no correct credit. Both constant binary baselines predict
on every cohort date. Supplied IDs must cover the full fixed cohort exactly.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def attainable_binary_skill_bound(
    cohort_case_ids: Sequence[str], forecast_labels: Mapping[str, str]
) -> dict[str, Any]:
    """Exact best possible credit margin over the better constant baseline.

    For N dates with R rain, D dry and A abstain forecasts, let T be the
    hypothetical number of actual rainy dates. At most min(R,T)+min(D,N-T)
    forecasts can be correct; the better constant earns max(T,N-T). Maximizing
    their difference over every integer T in [0,N] gives
    min(R,D,R+D-ceil(N/2)). It is attainable, not just an optimistic loose bound.

    Passing feasibility says only that some complete outcome vector could
    pass. It supplies no probability, observed accuracy or predictive evidence.
    The caller must independently verify that the supplied cohort was fixed;
    this function does not authenticate a seal, source or registration date.
    """
    if isinstance(cohort_case_ids, (str, bytes)) or not isinstance(
        cohort_case_ids, Sequence
    ):
        raise ValueError("Use the complete explicit sequence of cohort case IDs")
    cases = tuple(cohort_case_ids)
    if not cases or any(
        not isinstance(case, str) or not case.strip() for case in cases
    ):
        raise ValueError("A nonempty cohort with explicit string IDs is required")
    if len(set(cases)) != len(cases):
        raise ValueError("Duplicate cohort IDs cannot be silently collapsed")
    if not isinstance(forecast_labels, Mapping):
        raise ValueError("Forecasts must map explicit cohort IDs to fixed labels")
    labels = dict(forecast_labels)
    if any(not isinstance(case, str) or not case.strip() for case in labels):
        raise ValueError("Forecasts must map explicit cohort IDs to fixed labels")
    if set(labels) != set(cases):
        raise ValueError("Forecast IDs must cover the whole cohort exactly")
    if any(
        not isinstance(label, str) or label not in {"rain", "dry", "abstain"}
        for label in labels.values()
    ):
        raise ValueError("Use only rain, dry or explicit abstain; never infer a label")
    counts = Counter(labels.values())
    n = len(cases)
    rain, dry, abstain = (counts[k] for k in ["rain", "dry", "abstain"])
    categorical = rain + dry
    baseline_floor = (n + 1) // 2
    maximum_margin = min(rain, dry, categorical - baseline_floor)
    dominating = []
    if rain == 0:
        dominating.append("always_dry")
    if dry == 0:
        dominating.append("always_rain")
    return {
        "bound_id": "full_cohort_binary_constant_credit_bound_v1",
        "version": "1.0.0",
        "endpoint": "correct_credit_over_all_locked_days",
        "baseline": "better_of_always_rain_and_always_dry_over_full_cohort",
        "cohort_days": n,
        "forecast_counts": {"rain": rain, "dry": dry, "abstain": abstain},
        "maximum_possible_correct_credit": categorical,
        "better_constant_credit_lower_bound": baseline_floor,
        "exact_maximum_margin_over_better_constant": maximum_margin,
        "strictly_below_better_constant_for_every_complete_outcome_vector": (
            maximum_margin < 0
        ),
        "cannot_strictly_beat_better_constant_for_any_complete_outcome_vector": (
            maximum_margin <= 0
        ),
        "passing_is_possible_for_some_complete_binary_outcomes": maximum_margin > 0,
        "necessary_categorical_days_for_strict_superiority": baseline_floor + 1,
        "both_forecast_classes_necessary_for_strict_superiority": True,
        "constant_baselines_weakly_dominating_on_every_outcome_vector": dominating,
        "missing_forecasts_imputed": False,
        "observed_outcomes_used": False,
        "observed_accuracy": None,
        "supplied_cohort_seal_authenticated": False,
        "scope": "Conditional on this complete fixed forecast vector, binary complete outcomes, zero abstention credit and the specified full-cohort endpoint. Other models, inputs, targets or decision costs are not evaluated.",
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }


def audit_feasibility_vector(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    """Check the supplied file commitment; no prediction or outcome is changed."""
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_sha256)
    ):
        raise ValueError("Provide the previously recorded lowercase SHA-256")
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise ValueError("The supplied forecast vector differs from its commitment")

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON keys cannot hide a forecast or cohort")
            value[key] = item
        return value

    vector = json.loads(content, object_pairs_hook=unique_keys)
    if (
        not isinstance(vector, dict)
        or not {
            "cohort_case_ids",
            "forecast_labels",
        }
        <= vector.keys()
    ):
        raise ValueError("The vector must declare its full cohort and fixed labels")
    result = attainable_binary_skill_bound(
        vector["cohort_case_ids"], vector["forecast_labels"]
    )
    if path.read_bytes() != content:
        raise ValueError("The forecast vector changed during its audit")
    return {
        "vector_sha256": actual,
        "file_commitment_verified": True,
        "calculation_uses_only_cohort_ids_and_forecast_labels": True,
        "study_plan_or_timestamp_authenticated": False,
        "attainable_skill_bound": result,
    }
