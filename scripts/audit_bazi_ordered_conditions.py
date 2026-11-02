"""Audit the isolated hypothesis and factual review without adopting force rules."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fatebridge.core.output_stem_order_review import StemOrderSourceReview
from fatebridge.core.stem_order_review import stem_order_review_snapshot_line
from fatebridge.validation.agent_capture import canonical
from fatebridge.validation.case_capture import inspect_cases

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "docs/validation/bazi-ordered-conditions-files-v1"
FIXTURE = ROOT / "tests/fixtures/bazi_ordered_conditions_v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def captured(name: str) -> dict[str, Any]:
    with TemporaryDirectory() as folder:
        path = Path(folder) / "capture.jsonl"
        path.write_bytes(gzip.decompress((FILES / (name + ".jsonl.gz")).read_bytes()))
        return inspect_cases(path)


def reviews(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [r for v in value for r in reviews(v)]
    if not isinstance(value, dict):
        return []
    return [v for k, v in value.items() if k == "source_order_review"] + [
        r for k, v in value.items() if k != "source_order_review" for r in reviews(v)
    ]


def prior_facts(value: Any, lines: set[str], path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, list):
        return [prior_facts(v, lines, (*path, "[]")) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "source_order_review":
            StemOrderSourceReview.model_validate(item)
            if (
                item["candidate_numeric_policy_adopted"] is not False
                or item["calculation_effect"] != "none"
                or item["effective_combination"] != "not_adjudicated"
            ):
                raise ValueError(
                    "A source observation was promoted to numerical adoption"
                )
        elif isinstance(item, str) and (
            key == "snapshot_text"
            or (*path, key) == ("snapshot_export", "export_text")
            or (*path, key) == ("snapshot_export", "sections", "[]", "content")
        ):
            result[key] = "\n".join(
                line for line in item.split("\n") if line not in lines
            )
        else:
            result[key] = prior_facts(item, lines, (*path, key))
    return result


def audit() -> dict[str, Any]:
    baseline = captured("baseline-first")
    candidate = captured("candidate-first")
    production = captured("production-final")
    wheel = captured("wheel-final")
    public_before = captured("public-before-first")
    public_after = captured("public-production-final")
    public_wheel = captured("public-wheel-final")
    if not (
        baseline["inputs_sha256"]
        == candidate["inputs_sha256"]
        == production["inputs_sha256"]
        == wheel["inputs_sha256"]
    ):
        raise ValueError("Source corpus inputs or labels changed")
    if not (
        public_before["inputs_sha256"]
        == public_after["inputs_sha256"]
        == public_wheel["inputs_sha256"]
    ):
        raise ValueError("Public engineering inputs changed")
    if canonical(production["results"]) != canonical(wheel["results"]) or canonical(
        public_after["results"]
    ) != canonical(public_wheel["results"]):
        raise ValueError("Package results differ from final fixed source")
    cases = read(FILES / "registered-inputs-first.json")["cases"]
    unchanged = 0
    arithmetic_changed = 0
    improvements: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    nineteen = []
    review_candidates = 0
    for case, before, alternative, after in zip(
        cases,
        baseline["results"],
        candidate["results"],
        production["results"],
        strict=True,
    ):
        if canonical(before) != canonical(prior_facts(after, set())):
            raise ValueError("Old default facts or types changed: " + case["id"])
        old = before["strength"]["strength_level"]
        new = alternative["strength"]["strength_level"]
        expected = case["expected_strength"]
        row = {**case, "baseline_strength": old, "candidate_strength": new}
        if expected is not None:
            if old == expected and new != expected:
                regressions.append(row)
            if old != expected and new == expected:
                improvements.append(row)
        arithmetic_changed += canonical(
            before["strength"]["assessment"]["effective_elements_unrounded"]
        ) != canonical(
            alternative["strength"]["assessment"]["effective_elements_unrounded"]
        )
        unchanged += old == new
        review = after["strength"]["assessment"]["stem_energy_accounting"][
            "source_order_review"
        ]
        review_candidates += len(review["candidates"])
        if case["is_original_nineteen"]:
            if old == expected:
                raise ValueError("Original disagreement unexpectedly disappeared")
            nineteen.append(
                {
                    **row,
                    "production_strength": after["strength"]["strength_level"],
                    "source_order_review": review,
                }
            )
    snapshot_changes = 0
    for before, after in zip(
        public_before["results"], public_after["results"], strict=True
    ):
        lines = {
            line
            for r in reviews(after)
            if (line := stem_order_review_snapshot_line(r)) is not None
        }
        if canonical(before) != canonical(prior_facts(after, lines)):
            raise ValueError(
                "Public old facts changed beyond exactly declared review and supplied snapshot line"
            )
        snapshot_changes += before.get("snapshot_text") != after.get("snapshot_text")
    local = read(FIXTURE / "source-local-first.json")
    if len(cases) != 349 or len(nineteen) != 19 or len(public_after["results"]) != 22:
        raise ValueError("Declared cohort incomplete")
    if len(local["rows"]) != 3 or not all(
        r["candidate_matches"] for r in local["rows"]
    ):
        raise ValueError("Source-local partial layouts disappeared or failed")
    development = read(
        ROOT / "docs/validation/bazi-ordered-conditions-development-first-v1.json.gz"
    )
    if (
        development["arithmetic_changed_records"] != arithmetic_changed
        or development["label_changed_records"] != len(cases) - unchanged
        or canonical(development["new_matches"])
        != canonical(
            [
                r
                for r in development["rows"]
                if r["baseline_matches"] is False and r["candidate_matches"] is True
            ]
        )
        or len(improvements) != len(development["new_matches"])
        or len(regressions) != len(development["regressions"])
    ):
        raise ValueError("First experiment report changed")
    return {
        "scope": "Frozen v6: all 349 exposed records, 22 fictional public scenarios, 3 partial primary layouts. Historical scope; current v9 registry has 367 records. No independent force or real prediction validation.",
        "records": len(cases),
        "all_default_prior_facts_and_types_equal": True,
        "candidate_arithmetic_changed_records": arithmetic_changed,
        "candidate_label_changes": len(cases) - unchanged,
        "new_candidate_matches": improvements,
        "candidate_regressions": regressions,
        "factual_source_candidate_records": review_candidates,
        "source_local_layouts": local["rows"],
        "original_nineteen": nineteen,
        "public_scenarios": 22,
        "snapshots_with_only_declared_factual_line_added": snapshot_changes,
        "wheel_all_results_equal_to_final_source": True,
        "candidate_adopted": False,
        "fresh_full_chart_force_examples": 0,
        "original_no_paging8192_gate_passed": False,
        "v56_lost39_first_object_gate_passed": False,
        "new_actual_model_executions": 0,
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite an existing audit")
    result = audit()
    args.output.write_bytes(
        gzip.compress(
            json.dumps(result, ensure_ascii=False, indent=2).encode(), mtime=0
        )
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"original_nineteen", "source_local_layouts"}
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
