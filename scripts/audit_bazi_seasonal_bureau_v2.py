"""Evaluate a frozen seasonal-bureau hypothesis on a fully collated next unit."""

from __future__ import annotations

import argparse
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_seasonal_bureau_v2"
NEW_GROUP = "new_bage_and_previous_tail"
GROUPS = {
    "legacy": "tests/fixtures/bazi-strength-reference.json",
    "original": "tests/fixtures/bazi_classical_v1/cases.json",
    "hurt": "tests/fixtures/bazi_strength_expansion_v1/reference.json",
    "root": "tests/fixtures/bazi_root_force_experiment_v1/reference.json",
    "neutrality": "tests/fixtures/bazi_root_force_experiment_v2/reference.json",
    "passage": "tests/fixtures/bazi_root_force_experiment_v3/reference.json",
    "prior_root_v4": "tests/fixtures/bazi_root_force_experiment_v4/reference.json",
    "prior_stem_transformation": "tests/fixtures/bazi_stem_transformation_v1/reference.json",
    "prior_dizhi": "tests/fixtures/bazi_clash_season_v1/reference.json",
    "prior_ganzhi": "tests/fixtures/bazi_clash_season_v2/reference.json",
    "prior_shape_bureau": "tests/fixtures/bazi_clash_power_v3/reference.json",
    "prior_routes": "tests/fixtures/bazi_classical_routes_v1/reference.json",
    "prior_month_paths": "tests/fixtures/bazi_month_paths_v1/source-observations.json",
    "prior_month_addendum": "tests/fixtures/bazi_month_paths_v1/pdf85-addendum.json",
    "prior_month_cautions": "tests/fixtures/bazi_seasonal_bureau_v2/normalized-month-cautions.json",
    "new_dizhi": "tests/fixtures/bazi_seasonal_bureau_v2/reference.json",
}


class CoreRunner(Protocol):
    FIXTURE: Path
    GROUPS: dict[str, str]
    local_comparison: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

    def audit(self, candidate_root: Path) -> dict[str, Any]: ...

    def frozen_json(self, path: Path) -> Any: ...


class DirectionRunner(Protocol):
    def compare_direction(
        self, result: dict[str, Any], annotation: dict[str, Any]
    ) -> dict[str, Any]: ...


def load_runner(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        "_seasonal_bureau_" + name, ROOT / "scripts" / (name + ".py")
    )
    if spec is None or spec.loader is None:
        raise ValueError("Dependent runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def compare_application(
    result: dict[str, Any], annotation: dict[str, Any]
) -> dict[str, Any]:
    events = [
        e
        for e in result["relations"]
        if e["kind"] == "六冲" and set(e["positions"]) == set(annotation["positions"])
    ]
    if len(events) != 1 or events[0]["status"] not in {
        "active",
        "resolved_by_combination",
    }:
        return {"matches": None, "status": "not_comparable"}
    event = events[0]
    applied = event["status"] == "active"
    return {
        "matches": applied == (annotation["expected_clash_effect"] == "applied"),
        "status": "compared_application_flag_only",
        "model_event_status": event["status"],
        "root_damage_magnitude_adjudicated": False,
        "source_reason_adjudicated": False,
    }


def audit(candidate_root: Path) -> dict[str, Any]:
    core = cast(CoreRunner, load_runner("audit_bazi_clash_season"))
    directions = cast(DirectionRunner, load_runner("audit_bazi_clash_season_v2"))
    repair = core.frozen_json(FIXTURE / "runner-repair-v2.json")
    for relative, expected in repair["frozen_files"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError("Runner repair input changed: " + relative)
    original = json.loads((ROOT / repair["original_caution_source"]).read_text())
    for index, case in enumerate(original["cases"]):
        if "id" in case:
            raise ValueError("Original caution records changed")
        case["id"] = f"MONTH-CAUTION-{index + 1:02d}"
    normalized = json.loads((FIXTURE / "normalized-month-cautions.json").read_text())
    if normalized != original:
        raise ValueError("Normalization changed more than stable record identifiers")
    snapshot = core.frozen_json(
        ROOT / "tests/fixtures/bazi_strength_snapshot_v5/manifest.json"
    )
    candidate_root = candidate_root.resolve()
    before = {p: digest(candidate_root / p) for p in snapshot["files"]}
    if before != snapshot["files"]:
        raise ValueError("Full historical source differs from frozen v5 snapshot")
    core.FIXTURE = FIXTURE
    core.GROUPS = dict(GROUPS)
    core.local_comparison = directions.compare_direction
    result = core.audit(candidate_root)
    result["groups"][NEW_GROUP] = result["groups"].pop("new_dizhi")
    for row in result["groups"][NEW_GROUP]["rows"]:
        row["group"] = NEW_GROUP
    reference = core.frozen_json(FIXTURE / "reference.json")
    cases = {c["id"]: c for c in reference["cases"]}
    fresh_ids = {c["id"] for c in reference["cases"] if c["fresh_gate_eligible"]}
    fresh_rows = [
        r for r in result["groups"][NEW_GROUP]["rows"] if r["id"] in fresh_ids
    ]
    local, constraints, application = [], [], []
    for group, relative in GROUPS.items():
        if group == "new_dizhi":
            group = NEW_GROUP
        source = json.loads((ROOT / relative).read_text())
        if not isinstance(source, dict):
            continue
        rows = {r["id"]: r for r in result["groups"][group]["rows"]}
        for annotation in source.get("local_clash_labels", []):
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
                    "regressed": baseline["matches"] is True
                    and candidate["matches"] is not True,
                }
            )
        for condition in source.get("body_constraints", []):
            row = rows[condition["case_id"]]
            b, c = (
                row[k]["strength_level"] not in condition["forbidden_strengths"]
                for k in ("baseline", "candidate")
            )
            constraints.append(
                {
                    "group": group,
                    "source_condition": condition,
                    "baseline_matches": b,
                    "candidate_matches": c,
                    "regressed": b and not c,
                }
            )
        for condition in source.get("clash_application_conditions", []):
            row = rows[condition["case_id"]]
            baseline, candidate = (
                compare_application(row[k], condition)
                for k in ("baseline", "candidate")
            )
            application.append(
                {
                    "group": group,
                    "source_condition": condition,
                    "baseline": baseline,
                    "candidate": candidate,
                    "regressed": baseline["matches"] is True
                    and candidate["matches"] is not True,
                }
            )
    result["all_local_direction_comparisons"] = local
    result["all_negative_body_constraints"] = constraints
    result["clash_application_observations"] = application
    result["fresh_source_summary"] = {
        "chapter_cases": sum(c["source_unit"] == "八格" for c in cases.values()),
        "nonoverlap_cases": len(fresh_rows),
        "adjudicated": sum(r["expected_strength"] is not None for r in fresh_rows),
        "unknown": sum(r["expected_strength"] is None for r in fresh_rows),
        "resolved": [r["id"] for r in fresh_rows if r["resolved"]],
        "regressions": [r["id"] for r in fresh_rows if r["regressed"]],
        "previous_chapter_boundary_cases": sum(
            c["source_unit"] != "八格" for c in cases.values()
        ),
        "explicit_transformation_verdicts": 0,
    }
    # Neither 支类北方 nor 水势乘权 says a chemical transfer occurred. Do not
    # manufacture a formation pass from the candidate's own status field.
    result["adoption_gates"] = {
        "no_matching_body_label_regression": not any(
            r["regressed"] for g in result["groups"].values() for r in g["rows"]
        ),
        "no_matching_local_direction_regression": not any(
            r["regressed"] for r in local
        ),
        "no_matching_negative_body_regression": not any(
            r["regressed"] for r in constraints
        ),
        "no_matching_clash_application_regression": not any(
            r["regressed"] for r in application
        ),
        "new_nonoverlap_explicit_body_or_formation_improvement": any(
            r["resolved"] for r in fresh_rows
        ),
        "no_fresh_body_regression": not any(r["regressed"] for r in fresh_rows),
    }
    result["numerical_gates_passed"] = all(result["adoption_gates"].values())
    result["full_historical_source_before"] = before
    result["full_historical_source_after"] = {
        p: digest(candidate_root / p) for p in snapshot["files"]
    }
    if result["full_historical_source_after"] != before:
        raise ValueError("Historical source drift during comparison")
    result["boundary_addendum"] = reference["boundary_addendum"]
    result["source_annotation_scope"] = reference["annotation_policy"]
    result["formation_scope"] = (
        "No source-explicit full-transformation verdict on the only fresh complete "
        "seasonal bureau. Clash flags and directional proxies are reported "
        "separately; none certifies the author's force magnitude or cause."
    )
    result["runner_repair_sha256"] = digest(FIXTURE / "runner-repair-v2.json")
    result["runner_sha256"] = digest(Path(__file__))
    result["dependent_runners_sha256"] = {
        name: digest(ROOT / "scripts" / (name + ".py"))
        for name in ("audit_bazi_clash_season", "audit_bazi_clash_season_v2")
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the earlier comparison")
    result = audit(args.candidate_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                "groups": {
                    g: {k: v for k, v in data.items() if k != "rows"}
                    for g, data in result["groups"].items()
                },
                "fresh": result["fresh_source_summary"],
                "gates": result["adoption_gates"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["numerical_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
