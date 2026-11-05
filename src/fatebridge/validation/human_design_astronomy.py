"""Replay finite independent physical positions and independently solved roots."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from fatebridge.core.human_design_mechanics import longitude_activation, positions_at_tt
from fatebridge.core.human_design_time import solve_design_epoch_tt

LEVELS = ("gate", "line", "color", "tone", "base")


def horizons_anchor_checks(root: Path) -> dict[str, Any]:
    path = root / "tests/fixtures/human-design-astronomy-horizons.json"
    reference = json.loads(path.read_text())
    de440_path = root / "tests/fixtures/human-design-astronomy-de440.json"
    de440 = json.loads(de440_path.read_text())
    plan = json.loads((root / de440["plan_path"]).read_text())
    if (
        reference["de440_reference_sha256"]
        != hashlib.sha256(de440_path.read_bytes()).hexdigest()
        or reference["plan_sha256"] != de440["plan_sha256"]
        or reference["generator_sha256"]
        != hashlib.sha256(
            (
                root / "scripts/human_design/gen_human_design_astronomy_horizons.py"
            ).read_bytes()
        ).hexdigest()
        or reference["tolerance_arcseconds"] != 2.0
    ):
        raise ValueError("Frozen Horizons reference binding changed")
    expected_pairs = {
        (de440["pairs"][i]["label"], side): de440["pairs"][i][side]
        for i in plan["horizons_crosscheck"]["birth_indices"]
        for side in ("personality", "design")
    }
    records = reference["records"]
    if [r["body"] for r in records] != ["Sun", "Moon", "Pluto"]:
        raise ValueError("Frozen Horizons targets changed")
    checks = []
    for record in records:
        body = record["body"]
        if (
            hashlib.sha256(record["raw_response_utf8"].encode()).hexdigest()
            != record["raw_response_sha256"]
            or json.loads(record["raw_response_utf8"]) != record["response"]
            or record["parameters"]["TIME_TYPE"] != "'TT'"
            or record["parameters"]["COMMAND"] != f"'{plan['bodies'][body]}'"
        ):
            raise ValueError("Horizons raw response or target policy changed")
        table = record["response"]["result"].split("$$SOE")[1].split("$$EOE")[0].strip()
        raw_rows = list(csv.reader(io.StringIO(table)))
        if (
            len(raw_rows) != 6
            or len(record["rows"]) != 6
            or {(r["label"], r["side"]) for r in record["rows"]} != set(expected_pairs)
        ):
            raise ValueError("Incomplete fixed Horizons anchors")
        for raw, row in zip(raw_rows, record["rows"]):
            fact = expected_pairs[row["label"], row["side"]]
            longitude = float(raw[3])
            expected = fact["positions"][body]["longitude"]
            error = abs((longitude - expected + 180) % 360 - 180) * 3600
            if (
                float(raw[0]) != row["jd_tt"]
                or longitude != row["longitude"]
                or abs(row["jd_tt"] - fact["jd_tt"]) * 86400 > 0.001
                or row["skyfield_longitude"] != expected
                or row["error_arcseconds"] != error
            ):
                raise ValueError("Horizons transcription changed")
            checks.append(
                {
                    "body": body,
                    "label": row["label"],
                    "side": row["side"],
                    "error_arcseconds": error,
                    "within_tolerance": error <= 2.0,
                }
            )
    return {
        "status": (
            "bounded_horizons_anchors_matched"
            if all(r["within_tolerance"] for r in checks)
            else "failed"
        ),
        "observations_checked": len(checks),
        "maximum_error_arcseconds": max(r["error_arcseconds"] for r in checks),
        "rows": checks,
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scope": reference["scope"],
    }


def physical_astronomy_checks(root: Path) -> dict[str, Any]:
    path = root / "tests/fixtures/human-design-astronomy-de440.json"
    reference = json.loads(path.read_text())
    plan_path = root / reference["plan_path"]
    plan = json.loads(plan_path.read_text())
    if (
        len(plan["birth_epochs"]) != 122
        or len(reference["pairs"]) != 122
        or plan["comparison_tolerance_arcseconds"] != 2.0
        or plan["design_root_time_tolerance_seconds"] != 5.0
        or hashlib.sha256(plan_path.read_bytes()).hexdigest()
        != reference["plan_sha256"]
        or hashlib.sha256(
            (
                root / "scripts/human_design/gen_human_design_astronomy_reference.py"
            ).read_bytes()
        ).hexdigest()
        != reference["generator_sha256"]
    ):
        raise ValueError("Frozen astronomy reference, plan or tolerance changed")
    reports = {}
    for label, backend in (("selected", "swieph"), ("moshier_diagnostic", "moshier")):
        rows: list[dict[str, Any]] = []
        roots: list[dict[str, Any]] = []
        shifted: list[dict[str, Any]] = []
        for fixed, pair in zip(plan["birth_epochs"], reference["pairs"]):
            if fixed != {"label": pair["label"], "jd_tt": pair["personality"]["jd_tt"]}:
                raise ValueError("Fixed TT cohort changed")

            def compare(
                side: str, actual: dict[str, Any], *, own_root: bool = False
            ) -> None:
                target = shifted if own_root else rows
                expected_positions = pair[side]["positions"]
                if set(expected_positions) != set(plan["bodies"]):
                    raise ValueError("Incomplete independent body set")
                for body, fact in expected_positions.items():
                    if fact["target_id"] != plan["bodies"][body]:
                        raise ValueError("Independent body target changed")
                    a = actual[body]
                    error = (
                        abs((a["longitude"] - fact["longitude"] + 180) % 360 - 180)
                        * 3600
                    )
                    classifications = [
                        longitude_activation(x)
                        for x in (a["longitude"], fact["longitude"])
                    ]
                    target.append(
                        {
                            "label": pair["label"],
                            "side": side,
                            "body": body,
                            "ephemeris_model": a["ephemeris_model"],
                            "return_flags": a["return_flags"],
                            "error_arcseconds": error,
                            "within_tolerance": error <= 2.0,
                            "different_levels": [
                                k
                                for k in LEVELS
                                if classifications[0][k] != classifications[1][k]
                            ],
                        }
                    )

            for side in ("personality", "design"):
                compare(
                    side, positions_at_tt(pair[side]["jd_tt"], "true", backend=backend)
                )
            solver = solve_design_epoch_tt(
                pair["personality"]["jd_tt"], backend=backend
            )["solver"]
            error = abs(solver["design_jd_tt"] - pair["design"]["jd_tt"]) * 86400
            roots.append(
                {
                    "label": pair["label"],
                    "design_jd_tt": solver["design_jd_tt"],
                    "reference_design_jd_tt": pair["design"]["jd_tt"],
                    "error_seconds": error,
                    "within_tolerance": error <= 5.0,
                }
            )
            compare(
                "design",
                positions_at_tt(solver["design_jd_tt"], "true", backend=backend),
                own_root=True,
            )
        reports[label] = {
            "status": (
                "bounded_independent_physical_checks_passed"
                if all(r["within_tolerance"] for r in rows + roots)
                else "failed"
            ),
            "same_epoch_observations_checked": len(rows),
            "same_epoch_observations_within_tolerance": sum(
                r["within_tolerance"] for r in rows
            ),
            "maximum_same_epoch_error_arcseconds": max(
                r["error_arcseconds"] for r in rows
            ),
            "design_roots_checked": len(roots),
            "design_roots_within_tolerance": sum(r["within_tolerance"] for r in roots),
            "maximum_design_root_error_seconds": max(r["error_seconds"] for r in roots),
            "same_epoch_different_level_counts": {
                k: sum(k in r["different_levels"] for r in rows) for k in LEVELS
            },
            "own_root_design_different_level_counts": {
                k: sum(k in r["different_levels"] for r in shifted) for k in LEVELS
            },
            "models": sorted({r["ephemeris_model"] for r in rows}),
            "same_epoch_rows": rows,
            "design_root_rows": roots,
            "own_root_design_rows": shifted,
        }
    return {
        "method_id": reference["method_id"],
        "horizons_reference_pipeline_anchors": horizons_anchor_checks(root),
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "comparison_tolerance_arcseconds": 2.0,
        "design_root_time_tolerance_seconds": 5.0,
        "target_scope": reference["target_scope"],
        "scope": reference["scope"],
        **reports,
    }
