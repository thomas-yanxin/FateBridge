"""Independent ICRF directions from every original frozen calendar LBR fact.

No FateBridge/Swiss imports or new trajectory/root choices. Skyfield supplies
only the same of-date frame rotation used by the original reference generator.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import math
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/data/human_design/calendar_directions/evidence/plan.json"
REFERENCE_PATH = "tests/fixtures/human-design-calendar-span-de440.json"
OLD_PLAN_PATH = "tests/fixtures/human-design-calendar-span-plan.json"


def read(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)  # type: ignore[no-any-return]


def write(path: Path, value: dict) -> None:
    raw = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    with path.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)


def inputs() -> tuple[dict, dict, dict]:
    raw = PLAN.read_bytes()
    declared: dict = json.loads(raw)
    old_plan, reference = read(ROOT / OLD_PLAN_PATH), read(ROOT / REFERENCE_PATH)
    if (
        len(reference["pairs"]) != len(old_plan["birth_epochs"])
        or len(reference["pairs"]) != 1200
        or declared["expected_total_positions"] != 48000
    ):
        raise ValueError("All original pairs are required")
    if (
        declared["angular_tolerance_arcseconds"] != 2
        or old_plan["comparison_tolerance_arcseconds"] != 2
        or old_plan["design_root_time_tolerance_seconds"] != 5
    ):
        raise ValueError("Original numeric thresholds changed")
    for expected, pair in zip(
        old_plan["birth_epochs"], reference["pairs"], strict=True
    ):
        if expected != {"label": pair["label"], "jd_tt": pair["personality"]["jd_tt"]}:
            raise ValueError("Original birth label or TT rebound")
        for side in ("personality", "design"):
            if set(pair[side]["positions"]) != set(old_plan["bodies"]):
                raise ValueError("Original physical body omitted")
            for body, fact in pair[side]["positions"].items():
                if (
                    fact["target_id"] != old_plan["bodies"][body]
                    or not all(
                        type(fact[k]) in (int, float) and math.isfinite(fact[k])
                        for k in ("longitude", "latitude", "distance_au")
                    )
                    or not (
                        0 <= fact["longitude"] < 360
                        and -90 <= fact["latitude"] <= 90
                        and fact["distance_au"] > 0
                    )
                ):
                    raise ValueError("Invalid original physical target or LBR")
    return declared, old_plan, reference


def recover_icrf(matrix: list | tuple, value: list | tuple) -> list[float]:
    """Invert the stored matrix, without assuming exact floating orthogonality."""
    if (
        len(matrix) != 3
        or len(value) != 3
        or any(len(row) != 3 for row in matrix)
        or any(
            type(x) not in (int, float) or not math.isfinite(x)
            for x in [*value, *(x for row in matrix for x in row)]
        )
    ):
        raise ValueError("Invalid stored frame or direction")
    exact = [[Fraction(x) for x in row] for row in matrix]
    cofactors = []
    for i in range(3):
        row = []
        for j in range(3):
            a, b = [k for k in range(3) if k != i]
            c, d = [k for k in range(3) if k != j]
            row.append(
                (-1) ** (i + j)
                * (exact[a][c] * exact[b][d] - exact[a][d] * exact[b][c])
            )
        cofactors.append(row)
    determinant = sum(exact[0][j] * cofactors[0][j] for j in range(3))
    if determinant <= 0 or abs(float(determinant) - 1) > 1e-12:
        raise ValueError("Invalid stored rotation determinant")
    vector = [Fraction(x) for x in value]
    return [
        float(sum(cofactors[i][j] * vector[i] for i in range(3)) / determinant)
        for j in range(3)
    ]


def derive(output: Path) -> None:
    import numpy as np
    from skyfield.api import load  # type: ignore[import-untyped]
    from skyfield.framelib import ecliptic_frame  # type: ignore[import-untyped]

    if output.exists():
        raise FileExistsError(output)
    declared, old_plan, reference = inputs()
    for name, expected in declared["reference_runtime"].items():
        if version(name) != expected:
            raise ValueError("Changed reference runtime: " + name)
    package_files = {}
    for name in declared["reference_runtime"]:
        module = importlib.import_module(name)
        if module.__file__ is None:
            raise ValueError("Reference package has no readable origin: " + name)
        folder = Path(module.__file__).parent
        package_files.update(
            {
                name + "/" + str(p.relative_to(folder)): p
                for p in folder.rglob("*")
                if p.is_file()
                and not set(p.parts)
                & {"__pycache__", "tests", "testing", "benchmarks", "test-data"}
            }
        )
    before = {
        n: hashlib.sha256(p.read_bytes()).hexdigest()
        for n, p in sorted(package_files.items())
    }
    epochs = [
        (pair["label"], side, pair[side])
        for pair in reference["pairs"]
        for side in ("personality", "design")
    ]
    times = load.timescale(builtin=True).tt_jd(
        np.array([row["jd_tt"] for _, _, row in epochs])
    )
    matrices = ecliptic_frame.rotation_at(times)
    rows = []
    for index, (label, side, epoch) in enumerate(epochs):
        matrix = [[float(matrices[i, j, index]) for j in range(3)] for i in range(3)]
        directions = {}
        for body in old_plan["bodies"]:
            fact = epoch["positions"][body]
            lon, lat = map(math.radians, (fact["longitude"], fact["latitude"]))
            ecliptic = (
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
            )
            inertial = recover_icrf(matrix, ecliptic)
            directions[body] = {"original_fact": fact, "icrf_unit_vector": inertial}
        rows.append(
            {
                "label": label,
                "side": side,
                "jd_tt": epoch["jd_tt"],
                "icrf_to_original_ecliptic_rotation": matrix,
                "directions": directions,
            }
        )
    after = {
        n: hashlib.sha256(p.read_bytes()).hexdigest()
        for n, p in sorted(package_files.items())
    }
    if before != after:
        raise ValueError("Independent reference package changed during derivation")
    write(
        output,
        {
            "method_id": "human_design_all_original_calendar_icrf_directions_v2",
            "inverse_policy": "exact_rational_inverse_of_stored_binary64_matrix_times_exact_binary64_vector_then_one_final_rounding",
            "source_reference_sha256": declared["input_bindings"][REFERENCE_PATH],
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "versions": declared["reference_runtime"],
            "package_source_before": before,
            "package_source_after": after,
            "original_pair_count": 1200,
            "epoch_count": len(rows),
            "physical_direction_count": len(rows) * 10,
            "rows": rows,
            "new_trajectory_or_root_computed": False,
            "scope": "Inverse of the pinned original Skyfield of-date frame at the exact original TT. All original24,000 LBR facts retained; no new trajectory, Sun root, observer or target selection. Same-run package identities exclude tests/caches and do not prove all system/shared-library dependencies or astronomical truth.",
        },
    )
    print(
        "Independent recovered ICRF directions",
        len(rows) * 10,
        "epochs",
        len(rows),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    derive(parser.parse_args().output)
