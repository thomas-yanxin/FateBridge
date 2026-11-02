#!/usr/bin/env python3
"""Reproduce independent vectors using an unpacked, hash-verified NOAA C release."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    folder = Path(__file__).parents[1] / "tests/fixtures/fengshui_geomagnetic_v1"
    reference = json.loads((folder / "NOAA_C_100_main_field_values.json").read_text())
    source = args.source_dir.resolve()
    for name, expected in reference["source_hashes"].items():
        path = (
            folder / "noaa_c_wrapper.c" if name == "audit_wrapper.c" else source / name
        )
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"NOAA source/wrapper hash differs: {name}")
    rows = [
        line.split()[:4]
        for line in (folder / "NOAA_100_test_values.txt").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    if len(rows) != 100:
        raise ValueError("All 100 official inputs required")
    with tempfile.TemporaryDirectory(prefix="fatebridge-noaa-c-") as temporary:
        build = Path(temporary)
        shutil.copy2(folder / "noaa_c_wrapper.c", build / "audit_wrapper.c")
        for name in (
            "src/GeomagnetismLibrary.c",
            "src/GeomagnetismHeader.h",
            "data/WMM.COF",
        ):
            target = build / name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source / name, target)
        subprocess.run(
            [
                "cc",
                "-O2",
                "-Isrc",
                "audit_wrapper.c",
                "src/GeomagnetismLibrary.c",
                "-lm",
                "-o",
                "audit",
            ],
            cwd=build,
            check=True,
        )
        result = subprocess.run(
            [str(build / "audit")],
            cwd=build,
            input="\n".join(" ".join(row) for row in rows) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
    outputs = [list(map(float, line.split())) for line in result.stdout.splitlines()]
    if len(outputs) != 100 or any(len(row) != 7 for row in outputs):
        raise ValueError("Official C output incomplete")
    reference["vectors"] = [
        {"input_original": row, "field": dict(zip(reference["fields"], values))}
        for row, values in zip(rows, outputs)
    ]
    reference["environment"] = (
        "Reproduced locally with cc -O2; source files hash-verified unchanged"
    )
    args.output.write_text(json.dumps(reference, indent=2) + "\n")


if __name__ == "__main__":
    main()
