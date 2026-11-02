"""Freeze caller-supplied dice forecasts or audit them against observed outcomes.

This research CLI never invents a forecasting policy or treats its checks as
proof of predictive validity. Existing output files cannot be overwritten.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.validation.astrodice_study import (
    DiceObservation,
    FrozenDicePolicy,
    audit_study,
    engine_fingerprint,
    make_forecasts,
    policy_fingerprint,
)
from fatebridge.validation.predictions import Forecast, Outcome, StudyPlan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--policy", type=Path)
    for command in ("forecast", "audit"):
        child = sub.add_parser(command)
        for name in ("plan", "policy", "observations", "output"):
            child.add_argument("--" + name, type=Path, required=True)
        child.add_argument("--at", required=True)
        if command == "audit":
            child.add_argument("--forecasts", type=Path, required=True)
            child.add_argument("--outcomes", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fingerprint":
        value = {"symbolic_engine_sha256": engine_fingerprint()}
        if args.policy:
            value["policy_sha256"] = policy_fingerprint(
                FrozenDicePolicy.model_validate_json(args.policy.read_text())
            )
        print(json.dumps(value))
        return 0
    plan = StudyPlan.model_validate_json(args.plan.read_text())
    policy = FrozenDicePolicy.model_validate_json(args.policy.read_text())
    observations = [
        DiceObservation.model_validate(row)
        for row in json.loads(args.observations.read_text())
    ]
    at = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
    result: list[dict[str, Any]] | dict[str, Any]
    if args.command == "forecast":
        result = [
            f.model_dump(mode="json")
            for f in make_forecasts(plan, policy, observations, at=at)
        ]
    else:
        forecasts = [
            Forecast.model_validate(row)
            for row in json.loads(args.forecasts.read_text())
        ]
        outcomes = [
            Outcome.model_validate(row) for row in json.loads(args.outcomes.read_text())
        ]
        result = audit_study(plan, policy, observations, forecasts, outcomes, as_of=at)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps({"output": str(args.output), "predictive_validity_certified": False})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
