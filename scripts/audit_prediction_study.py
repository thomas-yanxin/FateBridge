"""Evaluate a registered study without generating forecasts or outcome labels."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from fatebridge.validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    evaluate_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--forecasts", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan = StudyPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
    forecasts = [
        Forecast.model_validate(row)
        for row in json.loads(args.forecasts.read_text(encoding="utf-8"))
    ]
    outcomes = [
        Outcome.model_validate(row)
        for row in json.loads(args.outcomes.read_text(encoding="utf-8"))
    ]
    report = evaluate_study(
        plan,
        forecasts,
        outcomes,
        as_of=datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "evaluable_count",
                    "coverage",
                    "preregistered_performance_gate_met",
                    "statistical_evidence_gate_met",
                    "real_world_efficacy",
                    "authority_certified",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
