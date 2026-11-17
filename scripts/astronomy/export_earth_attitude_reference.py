"""Export bounded original SOFA/Swiss controls from an external reference build.

No FateBridge import. The original source build, full reference arrays and
generators remain identified by content; this exports their selected data.
It does not regenerate an external reference from the implementation.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    source, destination = args.reference_directory, args.output_directory
    horizon = json.loads((source / "official-horizon-reference.json").read_text())
    houses = json.loads((source / "author-house-reference.json").read_text())
    sofa = json.loads((source / "sofa-build.json").read_text())
    swiss = json.loads((source / "author-swiss-build.json").read_text())
    rebase = json.loads((source / "solar-rebase-physical-reference.json").read_text())
    for name, digest in (
        ("official-horizon-reference.npz", horizon["reference_sha256"]),
        ("author-house-reference.npz", houses["reference_sha256"]),
    ):
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"External reference hash mismatch: {name}")
    epochs = []
    selected_epochs = [0, 1, 25, 50, 75, 100, 125, 150, 175, 200, 225, 256]
    with np.load(source / "author-house-reference.npz") as archive:
        for ordinal in range(len(archive["indices"])):
            ray = archive["source_rays"][ordinal, 1]
            epochs.append(
                {
                    "jd_ut1": float(archive["jd_ut1"][ordinal]),
                    "jd_tt": float(archive["jd_tt"][ordinal]),
                    "SOFA_NPB": archive["npb"][ordinal].tolist(),
                    "SOFA_GAST_degrees": math.degrees(
                        float(archive["gast_radians"][ordinal])
                    )
                    % 360,
                    "source_equatorial_Sun": [
                        math.degrees(math.atan2(ray[1], ray[0])) % 360,
                        math.degrees(math.atan2(ray[2], math.hypot(ray[0], ray[1]))),
                        float(np.linalg.norm(ray)),
                    ],
                }
            )
        cases = [
            {
                "epoch": int(row[0]),
                "house_code": houses["house_codes"][int(row[2])],
                "sidereal": bool(row[3]),
                "longitude": float(row[4]),
                "latitude": float(row[5]),
                "original_return_code": int(status),
                "values": values.tolist(),
            }
            for row, status, values in zip(
                archive["arguments"], archive["status"], archive["values"]
            )
            if int(row[0]) in selected_epochs
        ]
    generators = {
        name: (source / name).read_text()
        for name in (
            "generate_horizon_reference.py",
            "generate_house_reference.py",
            "official_frame_probe.c",
            "build_original_swiss.py",
            "generate_rebase_reference.py",
        )
    }
    reference = {
        "production_imported": False,
        "gate_arcseconds": houses["plan"]["cusp_and_angle_gate_arcseconds"],
        "epoch_count": len(epochs),
        "house_case_count": len(cases),
        "house_epoch_ordinals": selected_epochs,
        "selection": "Documented stratification after the full 141864-call comparison; not blind validation.",
        "scope": houses["scope"],
        "house_Sun_input_policy": "Freeze the original source ray for geometric tests; full external comparison also exercised actual source calls.",
        "reference_hashes": {
            "horizon": horizon["reference_sha256"],
            "houses": houses["reference_sha256"],
        },
        "SOFA_source_build": sofa,
        "Swiss_source_build": swiss,
        "generator_sources": generators,
        "generator_hashes": {
            name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in generators.items()
        },
        "epochs": epochs,
        "house_cases": cases,
        "solar_rebase": rebase,
    }
    destination.mkdir(parents=True, exist_ok=True)
    data = json.dumps(reference, ensure_ascii=False, separators=(",", ":")).encode()
    (destination / "reference.json.gz").write_bytes(gzip.compress(data, mtime=0))
    print(
        json.dumps(
            {
                "epochs": len(epochs),
                "house_cases": len(cases),
                "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
