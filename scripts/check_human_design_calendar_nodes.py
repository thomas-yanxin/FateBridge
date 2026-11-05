"""Original full cohort node checks, retaining every earlier physical failure.

The independent celestial reference is frozen before capture. Discrete fields
are projections through the existing engine mapping, not a new source oracle.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.core.human_design import longitude_activation, opposite_activation
from scripts.gen_human_design_calendar_nodes import BASE, inputs, read, sha, write

REFERENCE = BASE / "evidence/independent-nodes.json.gz"
REFERENCE_SHA256 = "75592092338443860801167c4e428f082f3412d25dabd7d88d5f8ecc3cc636d9"
LEVELS = ("gate", "line", "color", "tone", "base", "tone_orientation")


def reference() -> tuple[dict, dict, dict]:
    plan, cohort, controls = inputs()
    if sha(REFERENCE) != REFERENCE_SHA256:
        raise ValueError("Frozen independent node extension changed")
    value = read(REFERENCE)
    if (
        value["epoch_count"] != 2400
        or len(value["rows"]) != 2400
        or value["tolerance_arcseconds"] != 1.0
        or value["control_rows"] != controls["rows"]
        or value["original122_controls_exact"] is not True
        or value["generator_versions"] != plan["versions"]
        or value["kernel_sha256"] != plan["kernel_sha256"]
        or value["package_files_before"] != value["package_files_after"]
    ):
        raise ValueError("Independent node identity, controls or scope changed")
    expected = [
        (p["label"], side, p[side]["jd_tt"])
        for p in cohort["pairs"]
        for side in ("personality", "design")
    ]
    if [(r["label"], r["side"], r["jd_tt"]) for r in value["rows"]] != expected:
        raise ValueError("Independent original epoch or ordering changed")
    from scripts.check_human_design_calendar_directions import current_comparison

    return plan, value, current_comparison()


def _error(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def capture() -> dict:
    from fatebridge.core import human_design_natal_sources as sources
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design import positions_at_tt

    _, independent, _ = reference()
    trace = sources.NatalSourceTrace()
    token = sources._ACTIVE.set(trace)
    backends = {}
    try:
        for label, backend in (
            ("selected", "swieph"),
            ("moshier_diagnostic", "moshier"),
        ):
            rows = []
            for index, epoch in enumerate(independent["rows"]):
                seen: dict[str, dict] = {}

                def observe(body: str, tt: float, value: dict) -> None:
                    if tt != epoch["jd_tt"]:
                        raise ValueError("Native observer detached from requested TT")
                    seen[body] = dict(value)

                positions = None
                failure = None
                try:
                    positions = positions_at_tt(
                        epoch["jd_tt"],
                        "true",
                        backend=backend,
                        require_swiss_files=backend == "swieph",
                        source_observer=observe,
                    )
                except Exception as exc:
                    failure = _error(exc)
                rows.append(
                    {
                        "label": epoch["label"],
                        "side": epoch["side"],
                        "jd_tt": epoch["jd_tt"],
                        "requested_backend": backend,
                        "complete_batch_returned": failure is None,
                        "positions": positions,
                        "observed_prefix": seen,
                        "error": failure,
                    }
                )
                if (index + 1) % 200 == 0:
                    print(label, index + 1, flush=True)
            backends[label] = {"requested_backend": backend, "rows": rows}
        try:
            evidence, error = trace.finish(), None
        except Exception as exc:
            evidence, error = None, _error(exc)
    finally:
        sources._ACTIVE.reset(token)
    return {
        "method_id": "human_design_original_calendar_node_capture_v1",
        "native_version": str(runtime.swe.version),
        "independent_reference_sha256": REFERENCE_SHA256,
        "backends": backends,
        "source_evidence": evidence,
        "source_error": error,
        "native_execution_authenticated": False,
        "scope": "Fresh process of existing positions_at_tt, all13 returned positions and actual11-body observer prefixes. Earth/SouthNode are derived. Native flags and post-call file contexts retained; not a physical error bound or atomic read-set.",
    }


def compare_row(
    actual: dict, expected: dict, physical: list[dict], backend: str
) -> dict:
    result: dict[str, Any] = {
        "label": expected["label"],
        "side": expected["side"],
        "jd_tt": expected["jd_tt"],
        "requested_backend": backend,
        "reference_node_longitude": expected["node_longitude"],
        "computed_node_longitude": None,
        "error_arcseconds": None,
        "position_within_original1arcsecond": False,
        "actual_backend_and_batch_accepted": False,
        "different_levels_using_current_mapping": None,
        "node_projection_accepted": False,
        "original_physical_rows_accepted": all(r["accepted"] for r in physical),
        "original_physical_failure_indices": [
            r["original_index"] for r in physical if not r["accepted"]
        ],
        "fresh_physical_longitude_or_flag_differences": [],
        "all_fresh_physical_values_equal_original": False,
        "accepted_with_original_physical_rows": False,
        "evaluation_status": "not_assessed",
    }
    try:
        required = {r["body"] for r in physical} | {"NorthNode", "Earth", "SouthNode"}
        positions = actual["positions"]
        bit = {"swieph": 2, "moshier": 4}[backend]
        if (
            actual["error"] is not None
            or actual["complete_batch_returned"] is not True
            or not isinstance(positions, dict)
            or set(positions) != required
        ):
            raise ValueError("Incomplete actual13-position batch")
        if set(actual["observed_prefix"]) != required - {"Earth", "SouthNode"}:
            raise ValueError("Incomplete native11-body observer prefix")
        for body, value in actual["observed_prefix"].items():
            if (
                value != positions[body]
                or value["return_flags"] != bit | 256
                or value["ephemeris_model"] != backend
            ):
                raise ValueError("Native flag/backend/prefix inconsistency")
        node = positions["NorthNode"]
        if (
            node["native_return_flag_model"] != backend
            or type(node["longitude"]) is not float
            or not 0 <= node["longitude"] < 360
            or not math.isfinite(node["longitude_speed"])
        ):
            raise ValueError("Invalid actual node coordinate/model")
        actual_nodes = {
            "NorthNode": longitude_activation(node["longitude"]),
            "SouthNode": opposite_activation(node["longitude"]),
        }
        expected_nodes = {
            "NorthNode": longitude_activation(expected["node_longitude"]),
            "SouthNode": opposite_activation(expected["node_longitude"]),
        }
        for body, parent in (("Earth", "Sun"), ("SouthNode", "NorthNode")):
            derived = opposite_activation(positions[parent]["longitude"])
            if (
                positions[body]["derived_from"] != parent
                or positions[body]["derivation_source_longitude"]
                != positions[parent]["longitude"]
                or positions[body]["longitude"] != derived["longitude"]
            ):
                raise ValueError("Derived opposition detached from same-batch source")
        differences = {
            body: [
                level
                for level in LEVELS
                if actual_nodes[body][level] != expected_nodes[body][level]
            ]
            for body in actual_nodes
        }
        error = (
            abs(math.remainder(node["longitude"] - expected["node_longitude"], 360.0))
            * 3600
        )
        changed_physical = []
        for old in physical:
            before = old["longitude_comparison"]
            after = positions[old["body"]]
            if (before["computed_longitude"], before["return_flags"]) != (
                after["longitude"],
                after["return_flags"],
            ):
                changed_physical.append(
                    {
                        "body": old["body"],
                        "original_index": old["original_index"],
                        "old_longitude": before["computed_longitude"],
                        "new_longitude": after["longitude"],
                        "old_return_flags": before["return_flags"],
                        "new_return_flags": after["return_flags"],
                    }
                )
        result.update(
            computed_node_longitude=node["longitude"],
            return_flags=node["return_flags"],
            actual_backend_and_batch_accepted=True,
            error_arcseconds=error,
            position_within_original1arcsecond=error <= 1.0,
            different_levels_using_current_mapping=differences,
            node_projections={
                "actual": actual_nodes,
                "independent_reference": expected_nodes,
            },
            fresh_physical_longitude_or_flag_differences=changed_physical,
            all_fresh_physical_values_equal_original=not changed_physical,
            evaluation_status="observed",
        )
        result["node_projection_accepted"] = error <= 1.0 and not any(
            differences.values()
        )
        result["accepted_with_original_physical_rows"] = (
            result["node_projection_accepted"]
            and result["original_physical_rows_accepted"]
            and not changed_physical
        )
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        result["error"] = _error(exc)
    return result


def source_contexts_accepted(production: dict) -> bool:
    """Reconcile reported contexts, without claiming authenticated native reads."""
    try:
        source = production["source_evidence"]
        if (
            production["source_error"] is not None
            or source["method_id"] != "human_design_natal_native_file_contexts_v1"
            or source["status"] != "observed_contexts_endpoint_verified"
            or source["has_unidentified_sources"] is not False
            or source["configuration_checked"] is not True
            or source["endpoint_file_hashes_checked"] is not True
            or source["atomic_file_read_proven"] is not False
            or source["accuracy_certified"] is not False
            or source["native_execution_authenticated"] is not False
            or source["observed_native_position_evaluations"] != 52800
        ):
            return False
        files = {f["id"]: f for f in source["files"]}
        if len(files) != len(source["files"]) or not files:
            return False
        for key, row in files.items():
            if (
                key != f"se1:{row['slot']}:{row['sha256']}"
                or row["slot"] not in {0, 1}
                or len(row["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in row["sha256"])
                or type(row["bytes"]) is not int
                or row["bytes"] <= 0
                or any(
                    type(row[k]) not in (int, float) or not math.isfinite(row[k])
                    for k in ("start_julian_day_tt", "end_julian_day_tt")
                )
                or row["start_julian_day_tt"] >= row["end_julian_day_tt"]
                or type(row["de_number"]) is not int
                or row["de_number"] <= 0
            ):
                return False
        totals: Counter[tuple[str, str]] = Counter()
        seen = set()
        for row in source["contexts"]:
            model = row["native_return_flag_model"]
            if (
                row["role"] != "activation"
                or row["unresolved_slots"]
                or type(row["observed_evaluation_count"]) is not int
                or row["observed_evaluation_count"] <= 0
                or any(
                    type(row[k]) not in (int, float) or not math.isfinite(row[k])
                    for k in ("minimum_jd_tt", "maximum_jd_tt")
                )
                or row["minimum_jd_tt"] > row["maximum_jd_tt"]
            ):
                return False
            if model == "swieph":
                if (
                    row["status"] != "file_contexts_observed"
                    or len(row["file_ids"]) != 2
                    or any(f not in files for f in row["file_ids"])
                    or {files[f]["slot"] for f in row["file_ids"]} != {0, 1}
                ):
                    return False
            elif model == "moshier":
                if row["status"] != "library_builtin" or row["file_ids"]:
                    return False
            else:
                return False
            identity = (
                model,
                row["body"],
                row["role"],
                row["status"],
                tuple(sorted(row["file_ids"])),
            )
            if identity in seen:
                return False
            seen.add(identity)
            totals[(model, row["body"])] += row["observed_evaluation_count"]
        bodies = {
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
            "NorthNode",
        }
        return totals == {
            (model, body): 2400 for model in ("swieph", "moshier") for body in bodies
        }
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def compare(production: dict) -> dict:
    plan, independent, legacy = reference()
    if (
        production["method_id"] != "human_design_original_calendar_node_capture_v1"
        or production["independent_reference_sha256"] != REFERENCE_SHA256
        or set(production["backends"]) != {"selected", "moshier_diagnostic"}
    ):
        raise ValueError("Unknown or incomplete original node capture")
    source_accepted = source_contexts_accepted(production)
    backends = {}
    for label, backend in (("selected", "swieph"), ("moshier_diagnostic", "moshier")):
        observed = production["backends"][label]
        old_rows = legacy["backends"][label]["rows"]
        if (
            observed["requested_backend"] != backend
            or len(observed["rows"]) != 2400
            or len(old_rows) != 24000
        ):
            raise ValueError("Missing original node or physical rows")
        rows = []
        for i, (actual, expected) in enumerate(
            zip(observed["rows"], independent["rows"], strict=True)
        ):
            identity = (expected["label"], expected["side"], expected["jd_tt"])
            if (actual["label"], actual["side"], actual["jd_tt"]) != identity or actual[
                "requested_backend"
            ] != backend:
                raise ValueError("Original native epoch/order rebound")
            physical = [
                {**r, "original_index": 10 * i + j}
                for j, r in enumerate(old_rows[10 * i : 10 * i + 10])
            ]
            if len({r["body"] for r in physical}) != 10 or any(
                (r["label"], r["side"], r["jd_tt"]) != identity for r in physical
            ):
                raise ValueError("Original physical rows rebound to different epoch")
            rows.append(compare_row(actual, expected, physical, backend))
        backends[label] = {
            "rows": rows,
            "node_observation_count": len(rows),
            "not_assessed": sum(r["evaluation_status"] != "observed" for r in rows),
            "actual_backend_or_batch_rejection_count": sum(
                not r["actual_backend_and_batch_accepted"] for r in rows
            ),
            "position_failure_count": sum(
                not r["position_within_original1arcsecond"] for r in rows
            ),
            "different_level_counts": {
                level: sum(
                    level
                    in (r["different_levels_using_current_mapping"] or {}).get(body, [])
                    for r in rows
                    for body in ("NorthNode", "SouthNode")
                )
                for level in LEVELS
            },
            "within1arcsecond_but_discrete_differs": sum(
                r["position_within_original1arcsecond"]
                and any((r["different_levels_using_current_mapping"] or {}).values())
                for r in rows
            ),
            "node_projection_accepted_count": sum(
                r["node_projection_accepted"] for r in rows
            ),
            "original_physical_failure_count": sum(not r["accepted"] for r in old_rows),
            "all_fresh_physical_values_equal_original": all(
                r["all_fresh_physical_values_equal_original"] for r in rows
            ),
            "accepted_with_original_physical_rows_count": sum(
                r["accepted_with_original_physical_rows"] for r in rows
            ),
            "maximum_position_error_arcseconds": max(
                (
                    r["error_arcseconds"]
                    for r in rows
                    if r["error_arcseconds"] is not None
                ),
                default=None,
            ),
        }
    return {
        "method_id": "human_design_original_calendar_node_comparison_v1",
        "backends": backends,
        "source_contexts_accepted": source_accepted,
        "status": (
            "passed"
            if source_accepted
            and all(
                b["accepted_with_original_physical_rows_count"] == 2400
                for b in backends.values()
            )
            else "failed"
        ),
        "node_tolerance_arcseconds": plan["tolerance_arcseconds"],
        "original_physical_tolerance_arcseconds": 2.0,
        "original_root_tolerance_seconds": 5.0,
        "all_original_physical_failures_retained": True,
        "all_original_node_controls_retained": True,
        "original_roots_regraded": False,
        "new_independent_mean_node_evidence": False,
        "complete_continuous_calendar_certified": False,
        "official_human_design_node_convention_certified": False,
        "real_world_prediction_validated": False,
        "scope": "All original epochs and both backends retained. Position1arcsecond and exact discrete projection agreement separate; same mapping is not a fresh mandala/source oracle. Original full-direction failures never replaced by closer node values. No continuous error bound, mean-node, full source or prediction acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture_parser = sub.add_parser("capture")
    capture_parser.add_argument("--output", type=Path, required=True)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--production", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = capture() if args.command == "capture" else compare(read(args.production))
    write(args.output, value)
    summary = {
        k: v for k, v in value.items() if k not in {"backends", "source_evidence"}
    }
    if args.command == "compare":
        summary["backends"] = {
            k: {n: v for n, v in b.items() if n != "rows"}
            for k, b in value["backends"].items()
        }
    print(json.dumps(summary, ensure_ascii=False))
    return int(args.command == "compare" and value["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
