"""Replay the separately frozen whole-energy hypothesis without tuning or adoption."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_clash_power_v3"


class CoreRunner(Protocol):
    FIXTURE: Path
    GROUPS: dict[str, str]

    def audit(self, candidate_root: Path) -> dict[str, Any]: ...

    def frozen_json(self, path: Path) -> Any: ...


class DirectionRunner(Protocol):
    def compare_direction(
        self, result: dict[str, Any], annotation: dict[str, Any]
    ) -> dict[str, Any]: ...


def load_runner(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        "_power_v3_" + name, ROOT / "scripts" / (name + ".py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("Study runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(candidate_root: Path) -> dict[str, Any]:
    core = cast(CoreRunner, load_runner("audit_bazi_clash_season"))
    directions = cast(DirectionRunner, load_runner("audit_bazi_clash_season_v2"))
    core.FIXTURE = FIXTURE
    core.GROUPS = {
        **{k: v for k, v in core.GROUPS.items() if k != "new_dizhi"},
        "prior_dizhi": "tests/fixtures/bazi_clash_season_v1/reference.json",
        "prior_ganzhi": "tests/fixtures/bazi_clash_season_v2/reference.json",
        "new_dizhi": "tests/fixtures/bazi_clash_power_v3/reference.json",
    }
    result = core.audit(candidate_root)
    fresh_group = result["groups"]["new_shape_and_bureau"] = result["groups"].pop(
        "new_dizhi"
    )
    for row in fresh_group["rows"]:
        row["group"] = "new_shape_and_bureau"
    reference = core.frozen_json(FIXTURE / "reference.json")
    fresh_ids = {c["id"] for c in reference["cases"] if c["fresh_gate_eligible"]}
    fresh_rows = [r for r in fresh_group["rows"] if r["id"] in fresh_ids]
    local, constraints = [], []
    for group, version in (("prior_dizhi", 1), ("prior_ganzhi", 2)):
        source = core.frozen_json(
            ROOT / f"tests/fixtures/bazi_clash_season_v{version}/reference.json"
        )
        rows = {r["id"]: r for r in result["groups"][group]["rows"]}
        for annotation in source["local_clash_labels"]:
            row = rows[annotation["case_id"]]
            baseline, candidate = (
                directions.compare_direction(row[k], annotation)
                for k in ("baseline", "candidate")
            )
            local.append(
                {
                    "group": group,
                    "source_annotation": annotation,
                    "baseline": baseline,
                    "candidate": candidate,
                    "resolved": baseline["matches"] is False
                    and candidate["matches"] is True,
                    # Losing a previously comparable pass to unknown also
                    # requires review; it is not permitted to hide regression.
                    "regressed": baseline["matches"] is True
                    and candidate["matches"] is not True,
                }
            )
        for condition in source.get("body_constraints", []):
            row = rows[condition["case_id"]]
            baseline_ok, candidate_ok = (
                row[k]["strength_level"] not in condition["forbidden_strengths"]
                for k in ("baseline", "candidate")
            )
            constraints.append(
                {
                    "group": group,
                    "source_condition": condition,
                    "baseline_matches": baseline_ok,
                    "candidate_matches": candidate_ok,
                    "regressed": baseline_ok and not candidate_ok,
                }
            )
    result["previous_local_clash_comparisons"] = local
    result["previous_negative_body_constraints"] = constraints
    result["fresh_source_summary"] = {
        "new_cases": len(fresh_rows),
        "previous_chapter_boundary_addendum_cases": len(fresh_group["rows"])
        - len(fresh_rows),
        "adjudicated": sum(r["expected_strength"] is not None for r in fresh_rows),
        "unknown": sum(r["expected_strength"] is None for r in fresh_rows),
        "resolved": [r["id"] for r in fresh_rows if r["resolved"]],
        "regressions": [r["id"] for r in fresh_rows if r["regressed"]],
        "local_clash_labels": len(reference["local_clash_labels"]),
    }
    result["adoption_gates"].update(
        {
            "new_nonoverlap_body_or_local_clash_improvement": any(
                r["resolved"] for r in fresh_rows
            ),
            "no_previous_local_clash_regression": not any(
                r["regressed"] for r in local
            ),
            "no_previous_negative_body_regression": not any(
                r["regressed"] for r in constraints
            ),
            "no_fresh_body_regression": not any(r["regressed"] for r in fresh_rows),
        }
    )
    result["numerical_gates_passed"] = all(result["adoption_gates"].values())
    result["boundary_addendum"] = reference["boundary_addendum"]
    result["runner_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    result["dependent_runners_sha256"] = {
        name: sha256((ROOT / "scripts" / (name + ".py")).read_bytes()).hexdigest()
        for name in ("audit_bazi_clash_season", "audit_bazi_clash_season_v2")
    }
    result["source_annotation_scope"] = reference["annotation_policy"]
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
                "groups": {
                    k: {f: v for f, v in g.items() if f != "rows"}
                    for k, g in result["groups"].items()
                },
                "fresh_source": result["fresh_source_summary"],
                "gates": result["adoption_gates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
