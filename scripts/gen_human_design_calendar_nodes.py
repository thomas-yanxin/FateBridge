"""Extend the frozen independent DE440/ERFA node method to every original TT.

No FateBridge or Swiss import, native observations, output-selected epoch or
root replacement. Explicit maintenance; tests consume the frozen raw states.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-calendar-nodes-v1"
PLAN = BASE / "evidence/plan.json"
PLAN_SHA256 = "e645ad528f6b889d92da372a9be031df0b2ed4726a0d4ad7160b190ba21fc429"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    raw = path.read_bytes()
    value = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if not isinstance(value, dict):
        raise ValueError("A complete JSON object is required")
    return value


def write(path: Path, value: dict) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    with path.open("xb") as stream:
        stream.write(raw)


def inputs() -> tuple[dict, dict, dict]:
    if sha(PLAN) != PLAN_SHA256:
        raise ValueError("Node extension plan changed")
    plan = read(PLAN)
    names = (
        "tests/fixtures/human-design-calendar-span-plan.json",
        "tests/fixtures/human-design-calendar-span-de440.json",
        "tests/fixtures/human-design-node-de440.json",
        "scripts/gen_human_design_node_reference.py",
    )
    for name in names:
        if sha(ROOT / name) != plan["input_bindings"][name]:
            raise ValueError("Frozen independent input changed: " + name)
    declared, independent, controls = [read(ROOT / n) for n in names[:3]]
    if (
        len(declared["birth_epochs"]) != 1200
        or len(independent["pairs"]) != 1200
        or len(controls["rows"]) != 122
    ):
        raise ValueError("Incomplete original cohorts or altered tolerance")
    if plan["tolerance_arcseconds"] != 1.0 or controls["tolerance_arcseconds"] != 1.0:
        raise ValueError("Original1arcsecond node criterion changed")
    for actual, pair in zip(
        declared["birth_epochs"], independent["pairs"], strict=True
    ):
        if (actual["label"], actual["jd_tt"]) != (
            pair["label"],
            pair["personality"]["jd_tt"],
        ):
            raise ValueError("Original birth epoch or order changed")
    return plan, independent, controls


def package_files(modules: list[Any]) -> dict[str, str]:
    result = {}
    for module in modules:
        if module.__file__ is None:
            raise ValueError("Reference package file is unavailable")
        folder = Path(module.__file__).resolve().parent
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                result[module.__name__ + "/" + str(path.relative_to(folder))] = sha(
                    path
                )
    return result


def derive(kernel_path: Path) -> dict:
    import erfa  # type: ignore[import-untyped]
    import jplephem  # type: ignore[import-untyped]
    import numpy as np
    from jplephem.spk import SPK  # type: ignore[import-untyped]

    plan, independent, controls = inputs()
    versions = {name: version(name) for name in plan["versions"]}
    if versions != plan["versions"]:
        raise ValueError("Reference package versions differ from the frozen plan")
    kernel_before, code_before = sha(kernel_path), sha(Path(__file__))
    if (
        kernel_before != plan["kernel_sha256"]
        or hashlib.md5(kernel_path.read_bytes()).hexdigest() != plan["kernel_md5"]
    ):
        raise ValueError("DE440 identity changed")
    packages_before = package_files([erfa, jplephem, np])
    with SPK.open(kernel_path) as kernel:

        def state(jd_tdb: float) -> tuple[Any, Any]:
            moon = kernel[3, 301].compute_and_differentiate(
                2451545.0, jd_tdb - 2451545.0
            )
            earth = kernel[3, 399].compute_and_differentiate(
                2451545.0, jd_tdb - 2451545.0
            )
            return moon[0] - earth[0], moon[1] - earth[1]

        def fact(label: str, jd_tt: float) -> dict[str, Any]:
            tt2 = jd_tt - 2451545.0
            offset = float(erfa.dtdb(2451545.0, tt2, 0, 0, 0, 0))
            tdb1, tdb2 = erfa.tttdb(2451545.0, tt2, offset)
            jd_tdb = float(tdb1 + tdb2)
            r, v = state(jd_tdb)
            light_time = float(np.linalg.norm(r)) / 299792.458
            retarded = jd_tdb - light_time / 86400
            rr, vv = state(retarded)
            matrix = erfa.ecm06(2451545.0, tt2)
            dpsi = float(erfa.nut06a(2451545.0, tt2)[0])

            def node(position: Any, velocity: Any) -> float:
                normal = np.cross(matrix @ position, matrix @ velocity)
                return math.degrees(math.atan2(normal[0], -normal[1]) + dpsi) % 360

            return {
                "label": label,
                "jd_tt": jd_tt,
                "jd_tdb": jd_tdb,
                "tdb_minus_tt_seconds": offset,
                "geocentric_position_icrf_km": r.tolist(),
                "geocentric_velocity_icrf_km_per_day": v.tolist(),
                "light_time_seconds": light_time,
                "retarded_jd_tdb": retarded,
                "retarded_geocentric_position_icrf_km": rr.tolist(),
                "retarded_geocentric_velocity_icrf_km_per_day": vv.tolist(),
                "icrf_to_mean_ecliptic_of_date_matrix": matrix.tolist(),
                "nutation_longitude_radians": dpsi,
                "geometric_node_longitude": node(r, v),
                "node_longitude": node(rr, vv),
            }

        control_rows = [fact(row["label"], row["jd_tt"]) for row in controls["rows"]]
        controls_exact = control_rows == controls["rows"]
        rows = []
        for pair in independent["pairs"]:
            for side in ("personality", "design"):
                rows.append({"side": side, **fact(pair["label"], pair[side]["jd_tt"])})
        if len(rows) != 2400:
            raise ValueError("Incomplete original epoch cohort")
    packages_after = package_files([erfa, jplephem, np])
    if (
        packages_before != packages_after
        or kernel_before != sha(kernel_path)
        or code_before != sha(Path(__file__))
    ):
        raise ValueError(
            "Reference dependency, generator or kernel changed during generation"
        )
    return {
        "method_id": "human_design_original_calendar_de440_erfa_nodes_v1",
        "plan_sha256": PLAN_SHA256,
        "generator_sha256": code_before,
        "kernel_sha256": kernel_before,
        "kernel_bytes": kernel_path.stat().st_size,
        "generator_versions": versions,
        "package_files_before": packages_before,
        "package_files_after": packages_after,
        "same_run_dependency_identity_unchanged": True,
        "original122_controls_exact": controls_exact,
        "control_rows": control_rows,
        "epoch_count": 2400,
        "tolerance_arcseconds": 1.0,
        "rows": rows,
        "scope": "Same independent reference method over all original2400 TT epochs; raw geometric and light-time states retained. A finite seasonal cohort, not continuous precision, mean nodes, an official Human Design convention, full semantics or prediction. Raw states/versions and before/after hashes do not authenticate native or kernel truth.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = derive(args.kernel)
    write(args.output, value)
    print(
        json.dumps(
            {
                "epochs": value["epoch_count"],
                "original122_controls_exact": value["original122_controls_exact"],
                "package_files": len(value["package_files_before"]),
                "sha256": sha(args.output),
            }
        )
    )
    if not value["original122_controls_exact"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
