"""Bounded publisher example; keep missing-zone and absent-glyph limits explicit."""

import gzip
import hashlib
import json
import os
from contextlib import contextmanager
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, NoReturn
from unittest.mock import patch

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.public_output import same_public_value as _same_value
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-cycle-publisher-plan.json"
REFERENCE = (
    ROOT / "src/fatebridge/data/human_design/publisher-natal-2005-reference.json"
)
LEVELS = ("gate", "line", "color", "tone", "base")


@contextmanager
def backend_environment(path: Path) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in ("SE_EPHE_PATH", "FATEBRIDGE_JPL_FILE")}
    os.environ["SE_EPHE_PATH"] = str(path)
    os.environ.pop("FATEBRIDGE_JPL_FILE", None)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def forbidden(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("Publisher reading verification invoked native calculation")


def expected_cases(
    plan: dict[str, Any],
) -> list[tuple[str, dict[str, Any], str, str]]:
    return [
        (category, item, backend, mode)
        for backend in plan["backends"]
        for category in ("literal_hypotheses", "diagnostic_only_hypotheses")
        for item, mode in product(plan[category], plan["node_modes"])
    ]


def summarize_runs(plan: dict, reference: dict, runs: list[dict]) -> dict:
    specs = expected_cases(plan)
    if len(runs) != len(specs):
        raise ValueError("Missing or added publisher hypotheses")
    rows = []
    for row, (category, case, backend, mode) in zip(runs, specs, strict=True):
        if not _same_value(
            {k: row[k] for k in ("category", "id", "input", "backend", "mode")},
            {
                "category": category,
                "id": case["id"],
                "input": case["input"],
                "backend": backend,
                "mode": mode,
            },
        ):
            raise ValueError("Hypothesis identity, order or printed-clock role changed")
        run = row["run"]
        if run["calculation_policy"]["node_mode"] != mode:
            raise ValueError("Detached node convention")
        for side in ("personality", "design"):
            for a in run["activations"][side]:
                if (
                    a["body"] not in ("Earth", "NorthNode", "SouthNode")
                    and a["ephemeris_model"] != backend
                ):
                    raise ValueError("Requested physical backend was not observed")
        with (
            patch.object(runtime, "ephemeris_call", forbidden),
            patch.object(native_execution, "calculate", forbidden),
        ):
            check = verify_human_design_reading(run)
            sorted_check = verify_human_design_reading(
                json.loads(json.dumps(run, sort_keys=True))
            )
        if check["status"] != "verified_fixed_template_reading":
            raise ValueError("Complete publisher run failed fixed-reading verification")
        if sorted_check["status"] != "verified_fixed_template_reading":
            raise ValueError(
                "JSON object sorting changed complete reading verification"
            )
        observed = {
            "bodygraph.type": run["bodygraph"]["type"],
            "bodygraph.definition.kind": run["bodygraph"]["definition"]["kind"],
        }
        matches = observed == reference["example"]["expected_structural_fields"]
        rows.append(
            {
                "id": row["id"],
                "category": category,
                "backend": backend,
                "node_mode": mode,
                "input": case["input"],
                "observed_structural_fields": observed,
                "structural_match": matches,
                "counted_as_literal_comparison": category == "literal_hypotheses",
                "birth_tt": run["time_scales"]["personality"]["jd_tt"],
                "complete_fixed_reading_verified_without_native": True,
                "complete_sorted_roundtrip_verified_without_native": True,
            }
        )
    contrasts = []
    for backend, mode in product(plan["backends"], plan["node_modes"]):
        pair = [
            r
            for r in runs
            if r["category"] == "literal_hypotheses"
            and r["backend"] == backend
            and r["mode"] == mode
        ]
        a, b = [r["run"] for r in pair]
        changes = []
        for side in ("personality", "design"):
            for x, y in zip(
                a["activations"][side], b["activations"][side], strict=True
            ):
                assert x["body"] == y["body"]
                levels = [k for k in LEVELS if x[k] != y[k]]
                if levels:
                    changes.append(
                        {
                            "side": side,
                            "body": x["body"],
                            "levels": levels,
                            "first": {k: x[k] for k in LEVELS},
                            "second": {k: y[k] for k in LEVELS},
                        }
                    )
        contrasts.append(
            {
                "backend": backend,
                "node_mode": mode,
                "first_id": pair[0]["id"],
                "second_id": pair[1]["id"],
                "birth_tt_difference_seconds": (
                    b["time_scales"]["personality"]["jd_tt"]
                    - a["time_scales"]["personality"]["jd_tt"]
                )
                * 86400,
                "subdivision_changes": changes,
                "same_profile": a["profile"] == b["profile"],
                "same_incarnation_cross": a["incarnation_cross"]
                == b["incarnation_cross"],
                "same_variable_code": a["variables"]["code"] == b["variables"]["code"],
                "line_fixing_record_changes": [
                    {
                        "side": x["side"],
                        "body": x["body"],
                        "changed_fields": [k for k in x if x[k] != y[k]],
                        "first_fixing_state": x["fixing_state"],
                        "second_fixing_state": y["fixing_state"],
                    }
                    for x, y in zip(
                        a["depth_evidence"]["line_fixings"],
                        b["depth_evidence"]["line_fixings"],
                        strict=True,
                    )
                    if x != y
                ],
                "same_type_and_definition": all(
                    a["bodygraph"][k] == b["bodygraph"][k]
                    for k in ("type", "definition")
                ),
                "exact_epoch_or_activation_acceptance_inferred": False,
            }
        )
    literal = [r for r in rows if r["counted_as_literal_comparison"]]
    return {
        "method_id": "human_design_publisher_preview_natal_check_v1",
        "source": reference["source"],
        "independent_example_count": 1,
        "independent_structural_fact_count": 2,
        "literal_hypothesis_computation_count": len(literal),
        "literal_structure_matches": sum(r["structural_match"] for r in literal),
        "diagnostic_computation_count": len(rows) - len(literal),
        "diagnostic_matches_counted_as_acceptance": 0,
        "literal_structure_status": (
            "bounded_matches_under_explicit_zone_hypotheses"
            if all(r["structural_match"] for r in literal)
            else "failed"
        ),
        "publisher_time_zone_resolved": False,
        "exact_birth_epoch_accepted": False,
        "complete_activation_glyphs_accepted": False,
        "full_source_accepted": False,
        "prediction_sample_size": 0,
        "all_cases": rows,
        "literal_zone_contrasts": contrasts,
        "scope": "One direct publisher preview example with two structural assertions;16computations are not16independent examples. No source zone is invented, unprinted AM success is excluded from literal acceptance, and matching type/definition cannot certify the clock or all26activations. All original professional/source/physical failures remain separate.",
    }


def publisher_natal_checks(root: Path, *, capture: Path | None = None) -> dict:
    plan_path = root / "tests/fixtures/human-design-cycle-publisher-plan.json"
    reference_path = (
        root / "src/fatebridge/data/human_design/publisher-natal-2005-reference.json"
    )
    plan = json.loads(plan_path.read_text())
    reference = json.loads(reference_path.read_text())
    spec = next(s for s in CATALOG if s.key == "human_design")
    runs = []
    with TemporaryDirectory() as empty:
        for category, case, backend, mode in expected_cases(plan):
            with backend_environment(
                root / "ephe" if backend == "swieph" else Path(empty)
            ):
                run = execute_tool(
                    spec, spec.request_model(**case["input"], node_mode=mode)
                )
            runs.append(
                {
                    "category": category,
                    "id": case["id"],
                    "input": case["input"],
                    "backend": backend,
                    "mode": mode,
                    "run": run,
                }
            )
    report = summarize_runs(plan, reference, runs)
    report.update(
        {
            "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        }
    )
    if capture is not None:
        capture.write_bytes(
            gzip.compress(json.dumps(runs, sort_keys=True).encode(), mtime=0)
        )
        report["complete_capture_sha256"] = hashlib.sha256(
            capture.read_bytes()
        ).hexdigest()
    return report
