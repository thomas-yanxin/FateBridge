"""Freeze caller-supplied dice forecasts or audit them against observed outcomes."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

if __name__ == "__main__" and not __package__:
    # note (script entry): Direct execution needs the checkout for the research modules.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
else:
    pass

from validation.astrodice_study import (
    DiceObservation,
    FrozenDicePolicy,
    audit_study,
    engine_fingerprint,
    make_forecasts,
    policy_fingerprint,
)
from validation.predictions import Forecast, Outcome, StudyPlan


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
        else:
            pass
    args = parser.parse_args()
    if args.command == "fingerprint":
        value = {"symbolic_engine_sha256": engine_fingerprint()}
        if args.policy:
            value["policy_sha256"] = policy_fingerprint(
                FrozenDicePolicy.model_validate_json(args.policy.read_text())
            )
        else:
            pass
        print(json.dumps(value))
        return 0
    else:
        pass
    plan = StudyPlan.model_validate_json(args.plan.read_text())
    policy = FrozenDicePolicy.model_validate_json(args.policy.read_text())
    observations = TypeAdapter(list[DiceObservation]).validate_json(
        args.observations.read_bytes()
    )
    audit_time = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
    result: list[dict[str, JsonValue]] | dict[str, JsonValue]
    if args.command == "forecast":
        result = [
            forecast.model_dump(mode="json")
            for forecast in make_forecasts(plan, policy, observations, at=audit_time)
        ]
    else:
        forecasts = TypeAdapter(list[Forecast]).validate_json(
            args.forecasts.read_bytes()
        )
        outcomes = TypeAdapter(list[Outcome]).validate_json(args.outcomes.read_bytes())
        result = audit_study(
            plan, policy, observations, forecasts, outcomes, as_of=audit_time
        )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps({"output": str(args.output), "predictive_validity_certified": False})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
