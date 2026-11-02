"""Replay the frozen engine regression, optionally its entire ordered search.

This is an implementation check using Moshier, not independent astronomy. The
frozen case/plan are never rewritten. Wall-clock duration is not a golden value.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design import longitude_activation, positions_at_tt
from scripts.audit_human_design import transition_regression_checks


def replay_search(plan: dict, case: dict) -> dict:
    start = datetime.fromisoformat(plan["search_start_utc"])
    end = datetime.fromisoformat(plan["search_end_utc_exclusive"])
    origin = ephemeris_time(start).jd_tt

    def state(jd):
        positions = positions_at_tt(jd, "true", backend="moshier")
        result = {}
        for body, row in positions.items():
            if body in {"Earth", "SouthNode"}:
                continue
            activation = longitude_activation(row["longitude"])
            result[body] = [activation["gate"], activation["line"]] + (
                [activation["tone"]] if body in {"Sun", "NorthNode"} else []
            )
        return result

    previous = state(origin)
    found = None
    samples = 1
    for index in range(1, int((end - start).total_seconds() / plan["step_seconds"])):
        current = state(origin + index * plan["step_seconds"] / 86400)
        samples += 1
        changed = [body for body in previous if previous[body] != current[body]]
        if len(changed) >= 2:
            found = [
                origin + (index - 1) * plan["step_seconds"] / 86400,
                origin + index * plan["step_seconds"] / 86400,
            ]
            break
        previous = current
    return {
        "status": (
            "matched"
            if found == case["coarse_bracket_tt"]
            and samples == case["search_samples_checked"]
            else "failed"
        ),
        "samples_checked": samples,
        "first_bracket_tt": found,
        "scope": "First chronological personality-only two-dependency pair under the frozen plan. Not a success probability or astronomical oracle.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-search", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case_path = ROOT / "tests/fixtures/human-design-transition-case.json"
    case = json.loads(case_path.read_text())
    plan_path = ROOT / case["plan_path"]
    result = {"regression": transition_regression_checks()}
    if args.replay_search:
        result["ordered_search_replay"] = replay_search(
            json.loads(plan_path.read_text()), case
        )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.resolve() in {case_path.resolve(), plan_path.resolve()}:
            raise SystemExit("Cannot overwrite the frozen case or plan")
        args.output.write_text(text)
    else:
        print(text, end="")
    raise SystemExit(
        int(
            result["regression"]["status"] != "observed_transition_regression_passed"
            or (
                args.replay_search
                and result["ordered_search_replay"]["status"] != "matched"
            )
        )
    )


if __name__ == "__main__":
    main()
