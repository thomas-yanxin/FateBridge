"""Second complete chapter, same frozen candidate; retain the failed first study."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_clash_season_v2"


class FirstStudyRunner(Protocol):
    FIXTURE: Path
    GROUPS: dict[str, str]
    local_comparison: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

    def audit(self, candidate_root: Path) -> dict[str, Any]: ...

    def frozen_json(self, path: Path) -> Any: ...


def compare_direction(
    result: dict[str, Any], annotation: dict[str, Any]
) -> dict[str, Any]:
    """An explicit tie contradicts a strict source direction; absence is unknown."""
    pair = set(annotation["positions"])
    events = [
        event
        for event in result["relations"]
        if event["kind"] == "六冲" and set(event["positions"]) == pair
    ]
    if len(events) != 1:
        return {"status": "not_comparable", "matches": None}
    event = events[0]
    values = event.get("root_multipliers")
    if not values or set(values) != pair:
        return {
            "status": "not_comparable",
            "event_status": event["status"],
            "matches": None,
        }
    tied = len(set(values.values())) == 1
    weaker = None if tied else min(values, key=values.__getitem__)
    return {
        "status": "compared",
        "weaker_position": weaker,
        "model_direction": "tied" if tied else "unequal",
        "matches": weaker == annotation["weaker_position"],
        "root_multipliers": values,
    }


def audit(candidate_root: Path) -> dict[str, Any]:
    # Load a private, isolated copy of the original frozen runner. Its source,
    # v1 data and first results are not overwritten or relabeled.
    first_runner = ROOT / "scripts/audit_bazi_clash_season.py"
    spec = importlib.util.spec_from_file_location("_first_clash_study", first_runner)
    if spec is None or spec.loader is None:
        raise ValueError("Original study runner unavailable")
    loaded_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded_module)
    core = cast(FirstStudyRunner, loaded_module)
    core.FIXTURE = FIXTURE
    core.GROUPS = {
        **{k: v for k, v in core.GROUPS.items() if k != "new_dizhi"},
        "prior_dizhi": "tests/fixtures/bazi_clash_season_v1/reference.json",
        # The first runner's fresh-unit key is adapted below for this chapter.
        "new_dizhi": "tests/fixtures/bazi_clash_season_v2/reference.json",
    }
    core.local_comparison = compare_direction
    result = core.audit(candidate_root)
    result["groups"]["new_ganzhi"] = result["groups"].pop("new_dizhi")
    for row in result["groups"]["new_ganzhi"]["rows"]:
        row["group"] = "new_ganzhi"
    previous = core.frozen_json(
        ROOT / "tests/fixtures/bazi_clash_season_v1/reference.json"
    )
    earlier_rows = {r["id"]: r for r in result["groups"]["prior_dizhi"]["rows"]}
    previous_local = []
    for annotation in previous["local_clash_labels"]:
        row = earlier_rows[annotation["case_id"]]
        baseline_local, candidate_local = (
            compare_direction(row[k], annotation) for k in ("baseline", "candidate")
        )
        previous_local.append(
            {
                "source_annotation": annotation,
                "baseline": baseline_local,
                "candidate": candidate_local,
                "regressed": baseline_local["matches"] is True
                and candidate_local["matches"] is False,
            }
        )
    reference = core.frozen_json(FIXTURE / "reference.json")
    rows = {r["id"]: r for r in result["groups"]["new_ganzhi"]["rows"]}
    constraints = []
    for condition in reference["body_constraints"]:
        row = rows[condition["case_id"]]
        baseline_ok, candidate_ok = (
            row[k]["strength_level"] not in condition["forbidden_strengths"]
            for k in ("baseline", "candidate")
        )
        constraints.append(
            {
                "source_condition": condition,
                "baseline_matches": baseline_ok,
                "candidate_matches": candidate_ok,
                "regressed": baseline_ok and not candidate_ok,
            }
        )
    result["previous_local_clash_comparisons"] = previous_local
    result["new_negative_body_constraints"] = constraints
    result["adoption_gates"].update(
        {
            "no_previous_local_clash_regression": not any(
                r["regressed"] for r in previous_local
            ),
            "no_explicit_negative_body_regression": not any(
                r["regressed"] for r in constraints
            ),
        }
    )
    result["numerical_gates_passed"] = all(result["adoption_gates"].values())
    result["previous_study"] = core.frozen_json(FIXTURE / "protocol.json")[
        "previous_study"
    ]
    result["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    result["core_runner_sha256"] = sha256(first_runner.read_bytes()).hexdigest()
    result["local_direction_policy"] = (
        "Explicit active equal-retention decisions are mismatches when a source "
        "annotation requires unequal sides. Resolved/missing events remain "
        "not_comparable, never counted as passes. Root retention is an "
        "engineering proxy for a direction, not the source's numeric formula."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; preserve the first result")
    result = audit(args.candidate_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "body_groups": {
                    k: {f: v for f, v in g.items() if f not in {"rows"}}
                    for k, g in result["groups"].items()
                },
                "fresh_local": result["new_local_clash_comparisons"],
                "gates": result["adoption_gates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
