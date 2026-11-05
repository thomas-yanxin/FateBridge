"""Audit a frozen weather study; keep each evidence check and its gate separate."""

import argparse
import json
import sys
from pathlib import Path

from fatebridge.validation.meihua_weather_calendar_binding import (
    audit_calendar_bound_weather_study,
)
from fatebridge.validation.meihua_weather_context_capacity import (
    audit_context_capacity_study,
)
from fatebridge.validation.meihua_weather_solar_binding import (
    audit_solar_calendar_bound_weather_study,
)
from fatebridge.validation.meihua_weather_trace_binding import audit_bound_weather_study

AUDITS = {
    "trace": (audit_bound_weather_study, "mechanical_binding_verified"),
    "calendar": (
        audit_calendar_bound_weather_study,
        "published_lunar_date_binding_verified",
    ),
    "solar": (
        audit_solar_calendar_bound_weather_study,
        "published_solar_context_verified",
    ),
    "context-capacity": (audit_context_capacity_study, "context_capacity_verified"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=AUDITS, required=True)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-primary-potential-superiority", action="store_true")
    args = parser.parse_args()
    if args.require_primary_potential_superiority and args.check != "context-capacity":
        parser.error(
            "--require-primary-potential-superiority requires context-capacity"
        )
    audit, error_field = AUDITS[args.check]
    code = 0
    try:
        study, output = args.study.resolve(), args.output.resolve()
        if output.is_relative_to(study) or output.exists():
            raise ValueError(
                "Audit output must be a new file outside the immutable study"
            )
        result = audit(study)
        if args.check == "trace":
            summary = {
                "evidence_records": result["evidence_records"],
                "all_mechanical_bindings_verified": result[
                    "all_mechanical_bindings_verified"
                ],
                "outcomes_read": 0,
            }
        elif args.check == "calendar":
            summary = {
                "evidence_records": result["evidence_records"],
                "lunar_date_labels_verified": result["published_lunar_date_binding"][
                    "all_selected_date_labels_verified"
                ],
                "outcomes_read": 0,
            }
        elif args.check == "solar":
            bound = result["published_solar_context_binding"]
            summary = {
                "records": bound["evidence_records"],
                "counts": bound["counts"],
                "outcomes_read": 0,
            }
            code = (
                0 if bound["all_original_records_verified_under_declared_guard"] else 2
            )
        else:
            primary = next(
                row
                for row in result["cohort_scenario_reports"]
                if row["cohort"] == "primary_2026_ytd_through_last_complete_month"
                and row["scenario"] == "calendar_season_supplied"
            )
            oracle = next(
                row["bound"]
                for row in primary["context_oracle_families"]
                if row["family"] == "all_current_context_options"
            )
            possible = not oracle[
                "cannot_strictly_beat_better_constant_even_with_context_oracle"
            ]
            result["primary_capacity_requirement"] = {
                "required_by_command": args.require_primary_potential_superiority,
                "necessary_condition_only": True,
                "satisfied": possible,
                "predictive_efficacy_established": False,
            }
            summary = {
                "all_original_records": result["original_evidence_records"],
                "symbolic_context_cases": result["symbolic_context_domain"][
                    "symbolic_cases"
                ],
                "primary_oracle_maximum_margin": oracle[
                    "exact_maximum_margin_over_better_constant"
                ],
                "necessary_condition_satisfied": possible,
                "predictive_efficacy_established": False,
                "outcomes_read": 0,
            }
            code = (
                2 if args.require_primary_potential_superiority and not possible else 0
            )
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError, StopIteration) as exc:
        print(json.dumps({error_field: False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
