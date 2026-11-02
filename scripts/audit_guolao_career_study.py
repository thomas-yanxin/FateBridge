"""Analyze a registered paired career study; never invent its data or forecasts."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from fatebridge.validation.guolao_career import (
    METHOD,
    CareerOutcome,
    CareerStudyPlan,
    PairedCareerForecast,
    analysis_code_fingerprint,
    evaluate_career_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--forecasts", type=Path)
    parser.add_argument("--outcomes", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.schema:
        print(
            json.dumps(
                {
                    "method_id": METHOD,
                    "analysis_code_sha256": analysis_code_fingerprint(),
                    "plan": CareerStudyPlan.model_json_schema(),
                    "forecast": PairedCareerForecast.model_json_schema(),
                    "outcome": CareerOutcome.model_json_schema(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    for name in ("plan", "forecasts", "outcomes", "as_of", "output"):
        if getattr(args, name) is None:
            parser.error(
                "analysis requires --plan --forecasts --outcomes --as-of --output"
            )
    plan = CareerStudyPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
    forecasts = [
        PairedCareerForecast.model_validate(row)
        for row in json.loads(args.forecasts.read_text(encoding="utf-8"))
    ]
    outcomes = [
        CareerOutcome.model_validate(row)
        for row in json.loads(args.outcomes.read_text(encoding="utf-8"))
    ]
    report = evaluate_career_study(
        plan,
        forecasts,
        outcomes,
        as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "method_id",
                    "registered_count",
                    "observed_pair_count",
                    "explicit_abstention_count",
                    "outcome_pair_coverage",
                    "primary",
                    "real_world_efficacy",
                    "authority_certified",
                )
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
