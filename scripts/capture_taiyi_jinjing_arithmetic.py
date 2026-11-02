"""Capture current deterministic arithmetic; source values are never runtime outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from scripts.audit_taiyi_jinjing_arithmetic import FREEZE_SHA, ROOT, verify


def capture() -> dict[str, Any]:
    data = verify()
    from fatebridge.core.metaphysics import taiyi_year
    from fatebridge.core.metaphysics.taiyi_source_alignment import (
        count_source_assessment,
    )

    if not Path(taiyi_year.__file__).resolve().is_relative_to(ROOT / "src"):
        raise ValueError("实际生产模块不来自当前冻结工作目录")
    # Only parameter keys are consumed here; no reference count or term is used.
    keys = [(r["marker"], r["taiyi_number"]) for r in data["grid"]["controls"]]
    grid = [
        {
            "marker": marker,
            "taiyi_number": number,
            "trace": taiyi_year.count_to_taiyi(marker, number),
        }
        for marker, number in keys
    ]
    boards, assessments = [], []
    for row in data["source"]["rows"]:
        core = taiyi_year.cyclic_core(row["ju"], yin=row["yin"])
        boards.append({"id": row["id"], "core": core})
        assessments.append(
            {"id": row["id"], "assessment": count_source_assessment(core)}
        )
    fingerprints = {}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name:
            continue
        path = Path(name).resolve()
        if path.is_file() and path.is_relative_to(ROOT / "src"):
            fingerprints[str(path.relative_to(ROOT))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return {
        "reference_freeze_sha256": FREEZE_SHA,
        "count_grid": grid,
        "boards": boards,
        "assessments": assessments,
        "provenance": {
            "root": str(ROOT),
            "actual_ruleset": taiyi_year.RULESET_ID,
            "loaded_production_files": fingerprints,
            "capture_script_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "reference_expected_numbers_used_by_capture": False,
            "new_model_calls": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "count_controls": len(result["count_grid"]),
                "boards": len(result["boards"]),
                "new_models": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
