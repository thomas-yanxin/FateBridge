"""Evaluate a registered study without generating forecasts or outcome labels."""

import sys as _sys
from pathlib import Path as _Path

_VAL_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_VAL_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_VAL_REPO_ROOT))


import argparse
import json
from pathlib import Path

from pydantic import JsonValue, TypeAdapter

from fatebridge.utils.iso_clock import parse_iso_datetime
from validation.predictions import (
    Forecast,
    Outcome,
    StudyPlan,
    evaluate_study,
)


def load_json(path: Path) -> object:
    def unique_object(members: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in members:
            if key in result:
                raise ValueError(f"Duplicate JSON member: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--forecasts", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        plan = StudyPlan.model_validate(load_json(args.plan))
        forecasts = TypeAdapter(list[Forecast]).validate_python(
            load_json(args.forecasts)
        )
        outcomes = TypeAdapter(list[Outcome]).validate_python(load_json(args.outcomes))
        report = evaluate_study(
            plan,
            forecasts,
            outcomes,
            as_of=parse_iso_datetime(args.as_of.replace("Z", "+00:00")),
        )
    except ValueError as error:
        parser.error(str(error))
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
