"""Counterfactual no-deflector DE440 rows, separate from every original oracle."""

from __future__ import annotations

import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

from scripts.gen_human_design_calendar_horizons import KERNEL_SHA256, ROOT, plan

ABLATION_PLAN = (
    ROOT / "tests/data/human_design/calendar_horizons/evidence/ablation-plan.json"
)
ABLATION_SHA256 = "117ff676a27142f549f6d152005ce37424ee038d9124d1a0b9db58954211bb63"


def derive(output: Path) -> None:
    import numpy as np
    from skyfield.api import load, load_file  # type: ignore[import-untyped]
    from skyfield.framelib import ecliptic_frame  # type: ignore[import-untyped]

    if output.exists():
        raise FileExistsError(output)
    if hashlib.sha256(ABLATION_PLAN.read_bytes()).hexdigest() != ABLATION_SHA256:
        raise ValueError("Declared ablation changed")
    fixed = plan()
    for name, expected in fixed["reference_versions"].items():
        if version(name) != expected:
            raise ValueError("Independent reference dependency changed")
    path = ROOT / fixed["de440_kernel_path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != KERNEL_SHA256:
        raise ValueError("Independent kernel changed")
    kernel = load_file(str(path))
    try:
        ts = load.timescale(builtin=True)
        times = ts.tt_jd(np.array([r["jd_tt"] for r in fixed["epochs"]]))
        observer = kernel[399].at(times)
        records = []
        for body, target in fixed["bodies"].items():
            position = observer.observe(kernel[target]).apparent(deflectors=())
            lat, lon, distance = position.frame_latlon(ecliptic_frame)
            records.append(
                {
                    "body": body,
                    "target_id": target,
                    "rows": [
                        {
                            **r,
                            "longitude": float(lon.degrees[i]),
                            "latitude": float(lat.degrees[i]),
                            "distance_au": float(distance.au[i]),
                        }
                        for i, r in enumerate(fixed["epochs"])
                    ],
                }
            )
        value = {
            "method_id": "human_design_skyfield_no_deflectors_diagnostic_v1",
            "ablation_plan_sha256": ABLATION_SHA256,
            "kernel_sha256": KERNEL_SHA256,
            "versions": fixed["reference_versions"],
            "deflectors": [],
            "production_reference_replaced": False,
            "records": records,
        }
        output.write_text(json.dumps(value, indent=2) + "\n")
        print("diagnostic no-deflector rows", sum(len(r["rows"]) for r in records))
    finally:
        kernel.close()


if __name__ == "__main__":
    derive(Path(sys.argv[1]))
