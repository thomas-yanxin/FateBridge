"""Replay the frozen publisher lines under three separately accounted models."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, TypedDict

from fatebridge.core.human_design_mechanics import (
    longitude_activation,
    opposite_activation,
)
from fatebridge.services.human_design import calculate_human_design
from fatebridge.validation.human_design_publisher import backend_environment

COHORT_SHA256 = "3c92fb2aa7c3e018bc223cad59d6dbb26f5637fadf051a3d87ef11c371d84c34"
PLAN_SHA256 = "2ad8f1dd94abba5540b881369c61fe8df7937a6ed103139fca5f4d882997daf0"
ModelName = Literal["swieph", "moshier", "finite_source_point_mass"]
MODELS: tuple[ModelName, ...] = ("swieph", "moshier", "finite_source_point_mass")


class GateLineMismatch(TypedDict):
    side: str
    body: str
    expected: str
    actual: str


class ModelCase(TypedDict):
    id: str
    gate_lines_checked: int
    gate_lines_matched: int
    unassessed_gate_lines: int
    observed_native_models: list[str]
    mismatches: list[GateLineMismatch]


class ModelComparison(TypedDict):
    model: ModelName
    source_sha256: str
    plan_sha256: str
    planned_case_count: int
    observed_case_count: int
    missing_planned_ids: list[str]
    gate_lines_planned: int
    observed_cohort_gate_lines: int
    missing_case_gate_lines: int
    gate_lines_checked: int
    gate_lines_matched: int
    unassessed_gate_lines: int
    cases: list[ModelCase]
    complete_source_accepted: bool


class PointMassDirection(TypedDict):
    body: str
    longitude: float


def point_mass_gate_lines(positions: list[PointMassDirection]) -> dict[str, str]:
    activations = {
        position["body"]: longitude_activation(position["longitude"])
        for position in positions
    }
    sun_longitude_degrees = next(
        position["longitude"] for position in positions if position["body"] == "Sun"
    )
    activations["Earth"] = opposite_activation(sun_longitude_degrees)
    return {
        body: f"{activation['gate']}.{activation['line']}"
        for body, activation in activations.items()
    }


def compare_models(root: Path) -> list[ModelComparison]:
    source = (
        root / "tests/fixtures/human-design-disc-clock-observations.json"
    ).read_bytes()
    if hashlib.sha256(source).hexdigest() != COHORT_SHA256:
        raise ValueError("Frozen publisher observations differ from the pinned bytes")
    else:
        cohort = json.loads(source)
    plan_bytes = (
        root / "tests/fixtures/human-design-disc-clock-plan.json"
    ).read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != PLAN_SHA256:
        raise ValueError("Frozen publisher plan differs from the pinned bytes")
    else:
        plan = json.loads(plan_bytes)
    observed_ids = {case["id"] for case in cohort["cases"]}
    missing_ids = [
        case["id"] for case in plan["cases"] if case["id"] not in observed_ids
    ]
    reports: list[ModelComparison] = []
    with TemporaryDirectory() as empty:
        for model in MODELS:
            cases: list[ModelCase] = []
            for case in cohort["cases"]:
                with backend_environment(
                    Path(empty) if model == "moshier" else root / "ephe"
                ):
                    reading = calculate_human_design(
                        **case["birth_input"],
                        compare_apparent_models=model == "finite_source_point_mass",
                    )
                if "error" in reading:
                    raise RuntimeError(reading["error"])
                else:
                    observed: dict[tuple[str, str], str] = {}
                observed_models = sorted(
                    {
                        activation["ephemeris_model"]
                        for column in reading["activations"].values()
                        for activation in column
                        if activation["body"] not in ("Earth", "NorthNode", "SouthNode")
                    }
                )
                expected_backend = "moshier" if model == "moshier" else "swieph"
                if observed_models != [expected_backend]:
                    raise RuntimeError(
                        "Requested model differs from the observed native backend"
                    )
                else:
                    pass
                if model == "finite_source_point_mass":
                    comparison = reading["apparent_model_comparison"]
                    if comparison["candidate_design_root"]["status"] != "computed":
                        raise RuntimeError("Point-mass design root is unavailable")
                    else:
                        epochs = (
                            ("personality", comparison["epochs"]["personality"]),
                            ("design", comparison["candidate_design_epoch"]),
                        )
                    for side, epoch in epochs:
                        for body, gate_line in point_mass_gate_lines(
                            epoch["positions"]
                        ).items():
                            observed[side, body] = gate_line
                else:
                    for side, column in reading["activations"].items():
                        for activation in column:
                            observed[side, activation["body"]] = (
                                f"{activation['gate']}.{activation['line']}"
                            )
                mismatches: list[GateLineMismatch] = []
                checked = 0
                for side, column in case["columns"].items():
                    for body, expected in zip(
                        cohort["planet_order"], column, strict=True
                    ):
                        if (side, body) in observed:
                            checked += 1
                            actual = observed[side, body]
                            if actual != expected:
                                mismatches.append(
                                    {
                                        "side": side,
                                        "body": body,
                                        "expected": expected,
                                        "actual": actual,
                                    }
                                )
                            else:
                                pass
                        else:
                            pass
                cases.append(
                    {
                        "id": case["id"],
                        "gate_lines_checked": checked,
                        "gate_lines_matched": checked - len(mismatches),
                        "unassessed_gate_lines": 26 - checked,
                        "observed_native_models": observed_models,
                        "mismatches": mismatches,
                    }
                )
            reports.append(
                {
                    "model": model,
                    "source_sha256": COHORT_SHA256,
                    "plan_sha256": PLAN_SHA256,
                    "planned_case_count": len(plan["cases"]),
                    "observed_case_count": len(cases),
                    "missing_planned_ids": missing_ids,
                    "gate_lines_planned": 26 * len(plan["cases"]),
                    "observed_cohort_gate_lines": 26 * len(cases),
                    "missing_case_gate_lines": 26 * len(missing_ids),
                    "gate_lines_checked": sum(
                        case["gate_lines_checked"] for case in cases
                    ),
                    "gate_lines_matched": sum(
                        case["gate_lines_matched"] for case in cases
                    ),
                    "unassessed_gate_lines": 26 * len(missing_ids)
                    + sum(case["unassessed_gate_lines"] for case in cases),
                    "cases": cases,
                    "complete_source_accepted": False,
                }
            )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    reports = compare_models(Path(__file__).resolve().parents[2])
    report = {
        "method_id": "human_design_publisher_three_model_ledger_v1",
        "models": reports,
        "scope": "Original 13 observations from a 22-case plan; no source thresholds changed. Point-mass rows use that model's own design root and omit all 52 lunar-node lines; native nodes are never copied into it. Swiss barycentric inputs are shared, not independent physical observations. All nine missing cases remain unassessed in the full-plan counters. Literal names, historical clocks, physical accuracy and prediction remain outside this line ledger.",
    }
    with arguments.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            [
                {name: value for name, value in model.items() if name != "cases"}
                for model in reports
            ]
        )
    )


if __name__ == "__main__":
    main()
