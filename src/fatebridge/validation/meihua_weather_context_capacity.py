"""Outcome-free capacity of the pinned noon/weather-policy context family.

Context unions are an inadmissible oracle, not measured histories or forecasts.
A nonpositive oracle bound rules out strict superiority for this family/endpoint;
a positive bound neither authenticates contexts nor supplies predictive skill.
"""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fatebridge.core.divination import derive_meihua_hexagram
from fatebridge.core.meihua_weather import build_weather_interpretation
from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)
from fatebridge.validation.meihua_weather_feasibility import (
    attainable_binary_skill_bound,
)
from fatebridge.validation.meihua_weather_policy_v2 import canonical_sha256
from fatebridge.validation.meihua_weather_policy_v3 import scope_aware_weather_label
from fatebridge.validation.meihua_weather_reachability import (
    CONTROL_SHA256,
    POLICY_SOURCE_SHA256,
    PROFILE_SHA256,
    TRACE_KEYS,
)
from fatebridge.validation.meihua_weather_solar_binding import (
    audit_solar_calendar_bound_weather_study,
)
from fatebridge.validation.meihua_weather_trace_binding import STUDY_PINS

SEASONS = (None, "spring", "summer", "autumn", "winter")
PRIORS = (None, "prolonged_rain", "prolonged_clear", "neither_prolonged")
THRESHOLDS = (None, 2, 3, 4, 5, 6)
_LABELS = frozenset({"rain", "dry", "abstain"})
_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def context_oracle_credit_bound(
    cohort_case_ids: Sequence[str], capabilities: Mapping[str, Sequence[str]]
) -> dict[str, Any]:
    """Exact maximum over all allowed forecast choices and binary outcomes.

    Let r,d,b,a count rain-only, dry-only, both-class and only-abstain cases.
    M=r+d+b categorical choices can always be kept. The best balance of R,D
    is min(floor(M/2),r+b,d+b). Applying the original full-cohort constant
    bound gives min(that balance,M-ceil(N/2)). Context truth/availability and
    consistency across dates can only restrict this optimistic domain further.
    """
    if isinstance(cohort_case_ids, (str, bytes)) or not isinstance(
        cohort_case_ids, Sequence
    ):
        raise ValueError("Supply the whole explicit cohort sequence")
    cases = tuple(cohort_case_ids)
    if (
        not cases
        or any(not isinstance(x, str) or not x.strip() for x in cases)
        or len(set(cases)) != len(cases)
    ):
        raise ValueError("Retain nonempty unique cohort IDs")
    if not isinstance(capabilities, Mapping) or set(capabilities) != set(cases):
        raise ValueError("Capabilities must cover the full cohort exactly")
    counts: Counter[str] = Counter()
    both_ids = []
    witness = {}
    for case in cases:
        raw = capabilities[case]
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence) or not raw:
            raise ValueError("Each case needs explicit nonempty allowed labels")
        if any(not isinstance(x, str) or x not in _LABELS for x in raw) or len(
            set(raw)
        ) != len(raw):
            raise ValueError("Use unique rain/dry/abstain labels without imputation")
        present = set(raw)
        if {"rain", "dry"} <= present:
            counts["both"] += 1
            both_ids.append(case)
        elif "rain" in present:
            counts["rain_only"] += 1
            witness[case] = "rain"
        elif "dry" in present:
            counts["dry_only"] += 1
            witness[case] = "dry"
        else:
            counts["only_abstain"] += 1
            witness[case] = "abstain"
    r, d, b, a = (counts[k] for k in ["rain_only", "dry_only", "both", "only_abstain"])
    n = len(cases)
    categorical = r + d + b
    allocation = min(max(0, categorical // 2 - r), b)
    for index, case in enumerate(both_ids):
        witness[case] = "rain" if index < allocation else "dry"
    exact = min(categorical // 2, r + b, d + b, categorical - (n + 1) // 2)
    fixed = attainable_binary_skill_bound(cases, witness)
    if fixed["exact_maximum_margin_over_better_constant"] != exact:
        raise ValueError("Context capacity and original fixed-vector bound disagree")
    return {
        "bound_id": "meihua_inadmissible_context_oracle_credit_bound_v1",
        "endpoint": "unchanged_correct_credit_over_all_locked_days",
        "baseline": "unchanged_better_of_always_rain_and_always_dry",
        "cohort_days": n,
        "case_capability_counts": {
            "rain_only": r,
            "dry_only": d,
            "both": b,
            "only_abstain": a,
        },
        "maximum_possible_categorical_days": categorical,
        "exact_maximum_margin_over_better_constant": exact,
        "cannot_strictly_beat_better_constant_even_with_context_oracle": exact <= 0,
        "oracle_forecast_counts_witness": fixed["forecast_counts"],
        "oracle_forecast_sha256": canonical_sha256(witness),
        "oracle_is_an_admissible_forecasting_method": False,
        "context_values_measured_or_available_at_issue": False,
        "cross_date_context_consistency_enforced": False,
        "supplied_cohort_seal_authenticated": False,
        "context_option_set_authenticated_by_generic_bound": False,
        "positive_bound_establishes_predictive_skill": False,
        "outcome_data_used": False,
        "observed_accuracy": None,
        "predictive_efficacy_established": False,
    }


def audit_noon_context_domain() -> dict[str, Any]:
    """Exhaust all current declared contexts; do not select a favorable clock."""
    package = Path(__file__).resolve().parents[1]
    source = capture_package_sources(package)
    policy = package / "validation/meihua_weather_policy_v3.py"
    if hashlib.sha256(policy.read_bytes()).hexdigest() != POLICY_SOURCE_SHA256:
        raise ValueError("The pinned v3 label policy changed")
    rows: list[dict[str, Any]] = []
    counts: dict[tuple[str | None, int | None], Counter[str]] = {}
    for day in range(1, 25):
        cast = derive_meihua_hexagram(
            year_branch="子", lunar_month=1, lunar_day=day, hour_branch="午"
        )
        geometry = {
            "hour_number": 7,
            "s_residue": (day + 2) % 24,
            "representative_day": day,
            "representative_s": day + 2,
            "upper_number": cast["seed"]["upper_number"],
            "lower_number": cast["seed"]["lower_number"],
            "moving_line": cast["seed"]["moving_line"],
            "base_code": cast["base_hexagram"]["binary_code"],
            "mutual_code": cast["mutual_hexagram"]["binary_code"],
            "changed_code": cast["changed_hexagram"]["binary_code"],
        }
        for season, prior, threshold in itertools.product(SEASONS, PRIORS, THRESHOLDS):
            context = {
                "season": season,
                "prior_condition": prior,
                "many_min_count": threshold,
            }
            weather = build_weather_interpretation(cast, context)["weather"]
            decision = scope_aware_weather_label(
                weather,
                expected_profile_sha256=PROFILE_SHA256,
                expected_control_profile_sha256=CONTROL_SHA256,
            )
            traces = {r["rule_id"]: r for r in weather["rule_trace"]}
            requirements = {
                r["id"]: r["conditions"]["prior_condition"]
                for r in weather["ruleset"]["rules"]
                if "prior_condition" in r["conditions"]
            }
            prior_rows = [
                {
                    "rule_id": rid,
                    "required_prior": required,
                    **{
                        k: traces[rid][k]
                        for k in [
                            "status",
                            "effective_status",
                            "effective_tags",
                            "conditional_tags",
                            "control_checks",
                        ]
                    },
                }
                for rid, required in requirements.items()
            ]
            rows.append(
                {
                    "geometry": geometry,
                    "context": context,
                    "decision": decision,
                    "trace_sha256": canonical_sha256(
                        {k: weather[k] for k in TRACE_KEYS}
                    ),
                    "decision_sha256": canonical_sha256(decision),
                    "prior_clause_qualifications": prior_rows,
                }
            )
            counts.setdefault((prior, threshold), Counter())[decision["label"]] += 1
    if (
        len(rows) != 2880
        or len({(r["geometry"]["s_residue"], *r["context"].values()) for r in rows})
        != 2880
    ):
        raise ValueError("Retain the full24 residues times120 declared contexts")
    verify_package_sources(package, source)
    return {
        "audit_id": "meihua_noon_weather_context_domain_v1",
        "version": "1.0.0",
        "weather_profile_canonical_sha256": PROFILE_SHA256,
        "control_profile_canonical_sha256": CONTROL_SHA256,
        "label_policy_source_sha256": POLICY_SOURCE_SHA256,
        "fixed_hour_branch": "午",
        "hour_selection_performed": False,
        "arithmetic_residues": 24,
        "context_patterns": 120,
        "symbolic_cases": 2880,
        "period_proof": "S+24 preserves mod8 upper/lower and mod6 moving line; actual date/season combinations are a subset",
        "rows": rows,
        "all24_prior_threshold_summaries": [
            {
                "prior_condition": p,
                "many_min_count": m,
                "cases_including_all5_season_states": 120,
                "label_counts": {
                    k: counts[(p, m)][k] for k in ["rain", "dry", "abstain"]
                },
            }
            for p, m in itertools.product(PRIORS, THRESHOLDS)
        ],
        "source_sha256": source,
        "source_guard_held": True,
        "context_values_are_counterfactual_not_actual_observations": True,
        "unknown_prior_is_not_neither": True,
        "number_of_days_for_久_inferred": False,
        "threshold_is_unique_original_text_rule": False,
        "old_negative_results_known_not_blind": True,
        "real_calendar_date_witness_established": False,
        "new_real_world_observations": 0,
        "independent_model_executions": 0,
        "predictive_efficacy_established": False,
    }


def audit_context_capacity_study(directory: Path) -> dict[str, Any]:
    """Retain every original cohort/scenario; no observed rainfall is read."""
    directory = directory.resolve()
    original = audit_solar_calendar_bound_weather_study(directory)
    grid = audit_noon_context_domain()
    lookup = {
        (
            r["geometry"]["s_residue"],
            r["context"]["season"],
            r["context"]["prior_condition"],
            r["context"]["many_min_count"],
        ): r
        for r in grid["rows"]
    }
    candidates = [
        (directory / p).resolve()
        for p in ["generated/evidence.jsonl", "generated/evidence.jsonl.gz"]
    ]
    if (
        any(not p.is_relative_to(directory) for p in candidates)
        or sum(p.exists() for p in candidates) != 1
    ):
        raise ValueError("Use exactly one in-directory original evidence file")
    path = next(p for p in candidates if p.exists())
    opener = gzip.open if path.suffix == ".gz" else open
    digest = hashlib.sha256()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    baseline_matches = 0
    for raw in opener(path, "rb"):
        digest.update(raw)
        row = json.loads(raw)
        if (
            row["input"]["analysis_hour"] != 12
            or row["input"]["analysis_minute"] != 0
            or row["seed"]["hour_branch"] != "午"
        ):
            raise ValueError("Retain the original noon issue clock")
        context = row["input"].get("weather_context") or {}
        if (
            context.get("prior_condition") is not None
            or context.get("many_min_count") is not None
        ):
            raise ValueError("Original missing context cannot be rewritten")
        seed = row["seed"]
        residue = (
            _BRANCHES.index(seed["year_branch"])
            + 1
            + seed["lunar_month"]
            + seed["lunar_day"]
        ) % 24
        season = context.get("season")
        baseline = lookup[(residue, season, None, None)]
        geometry = baseline["geometry"]
        if (
            any(
                geometry[k] != row[k]
                for k in ["base_code", "mutual_code", "changed_code"]
            )
            or geometry["moving_line"] != seed["moving_line"]
        ):
            raise ValueError("Stored cast and symbolic residue are inconsistent")
        if baseline["decision"] != row["decision"]:
            raise ValueError("Retain every original decision without relabelling")
        baseline_matches += 1
        options = {
            (p, m): lookup[(residue, season, p, m)]["decision"]["label"]
            for p, m in itertools.product(PRIORS, THRESHOLDS)
        }
        groups.setdefault((row["cohort"], row["scenario"]), []).append(
            {"case_id": row["date"], "options": options}
        )
    if (
        digest.hexdigest() != STUDY_PINS["generated/evidence.jsonl"]
        or baseline_matches != original["evidence_records"]
    ):
        raise ValueError("Retain the complete original evidence and decision set")
    families = {
        "known_priors_many_still_unknown": list(itertools.product(PRIORS[1:], [None])),
        "many_declared_prior_unknown": list(itertools.product([None], THRESHOLDS[1:])),
        "known_prior_and_many_declared": list(
            itertools.product(PRIORS[1:], THRESHOLDS[1:])
        ),
        "all_current_context_options": list(itertools.product(PRIORS, THRESHOLDS)),
    }
    reports = []
    for (cohort, scenario), rows in sorted(groups.items()):
        ids = [r["case_id"] for r in rows]
        baseline = {r["case_id"]: r["options"][(None, None)] for r in rows}
        reports.append(
            {
                "cohort": cohort,
                "scenario": scenario,
                "cohort_days": len(rows),
                "original_fixed_vector_bound": attainable_binary_skill_bound(
                    ids, baseline
                ),
                "all24_homogeneous_counterfactual_declarations": [
                    {
                        "prior_condition": p,
                        "many_min_count": m,
                        "bound": attainable_binary_skill_bound(
                            ids, {r["case_id"]: r["options"][(p, m)] for r in rows}
                        ),
                        "factual_forecast_claimed": False,
                    }
                    for p, m in itertools.product(PRIORS, THRESHOLDS)
                ],
                "context_oracle_families": [
                    {
                        "family": name,
                        "bound": context_oracle_credit_bound(
                            ids,
                            {
                                r["case_id"]: sorted(
                                    {r["options"][option] for option in options}
                                )
                                for r in rows
                            },
                        ),
                    }
                    for name, options in families.items()
                ],
                "oracle_selection_is_admissible": False,
            }
        )
    for name, expected in STUDY_PINS.items():
        p = (directory / name).resolve()
        if not p.is_relative_to(directory):
            raise ValueError("Study path escapes its immutable directory")
        if (
            name != "generated/evidence.jsonl"
            and hashlib.sha256(p.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Original study changed during capacity analysis")
    return {
        "audit_id": "meihua_original_noon_study_context_capacity_v1",
        "version": "1.0.0",
        "original_evidence_records": baseline_matches,
        "all_original_decisions_unchanged": True,
        "original_solar_calendar_report": original,
        "symbolic_context_domain": grid,
        "cohort_scenario_reports": reports,
        "all_original_groups_retained": len(reports) == 6,
        "source_conditions_actually_observed_or_available_at_issue": False,
        "forecast_labels_contexts_or_scores_replaced": False,
        "context_oracle_is_a_prospective_forecast": False,
        "outcome_files_read": 0,
        "independent_model_executions": 0,
        "new_real_world_observations": 0,
        "predictive_efficacy_established": False,
        "authority_certified": False,
    }
