"""Exhaust the pinned noon weather context family without rainfall outcomes."""

import argparse
import json
import sys
from pathlib import Path

from fatebridge.validation.meihua_weather_context_capacity import (
    audit_context_capacity_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-primary-potential-superiority", action="store_true")
    args = parser.parse_args()
    try:
        study = args.study.resolve()
        output = args.output.resolve()
        if output.is_relative_to(study) or output.exists():
            raise ValueError(
                "Capacity output must be a new file outside the immutable study"
            )
        result = audit_context_capacity_study(study)
        primary = next(
            r
            for r in result["cohort_scenario_reports"]
            if r["cohort"] == "primary_2026_ytd_through_last_complete_month"
            and r["scenario"] == "calendar_season_supplied"
        )
        oracle = next(
            r["bound"]
            for r in primary["context_oracle_families"]
            if r["family"] == "all_current_context_options"
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
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError, StopIteration) as exc:
        print(
            json.dumps(
                {"context_capacity_verified": False, "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
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
        )
    )
    return 2 if args.require_primary_potential_superiority and not possible else 0


if __name__ == "__main__":
    raise SystemExit(main())
