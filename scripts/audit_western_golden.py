"""Verify classified Western snapshots on the canonical Linux environment.

This is regression evidence, not an independent astronomy oracle. It never
updates snapshots; changes must be reviewed separately before establishing a
new baseline. Run with the locked development dependencies on Linux x86_64 and
the Python minor version required by tests.golden.runner.
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from fatebridge.api import app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.golden.canonical import canonical_json
from tests.golden.runner import (
    freeze_clock,
    golden_ephemeris,
    is_baseline_environment,
)

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/validation/western-three-axis-requirements.json"


def audit():
    if not is_baseline_environment():
        raise RuntimeError("Western byte comparison requires the canonical environment")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    keys = {
        item["key"]
        for item in inventory["published_western_surface_inventory"]
        if item["alias_of"] is None
    }
    specs = [spec for spec in CATALOG if spec.key in keys and spec.rest_path]
    if {spec.key for spec in specs} != keys:
        raise RuntimeError("The Western inventory and REST surface selection differ")
    rows = []
    with golden_ephemeris(), freeze_clock(), TestClient(app) as client:
        for spec in specs:
            inputs = REST_POST_CASES[spec.rest_path]()
            response = client.post(spec.rest_path, json=inputs)
            if response.status_code != 200:
                raise RuntimeError(f"{spec.key} returned HTTP {response.status_code}")
            encoded = canonical_json(response.json()) + "\n"
            business = {
                key: value
                for key, value in json.loads(encoded).items()
                if key != "run_metadata"
            }
            spec.output_model.model_validate(business)
            Draft202012Validator(spec.output_model.model_json_schema()).validate(
                business
            )
            filename = spec.rest_path.strip("/").replace("/", "_") + ".json"
            snapshot = ROOT / "tests/golden/snapshots" / filename
            rows.append(
                {
                    "key": spec.key,
                    "file": filename,
                    "input": inputs,
                    "actual_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                    "expected_sha256": hashlib.sha256(
                        snapshot.read_bytes()
                    ).hexdigest(),
                    "matched": snapshot.read_bytes() == encoded.encode(),
                }
            )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system() + "-" + platform.machine(),
        "python": sys.version,
        "inventory_sha256": hashlib.sha256(INVENTORY.read_bytes()).hexdigest(),
        "matched_count": sum(row["matched"] for row in rows),
        "selected_count": len(rows),
        "scope": "Classified Western REST fixtures; aliases are not extra evidence",
        "independent_astronomical_oracle": False,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
        print(
            f"Western snapshots: {report['matched_count']}/{report['selected_count']}"
        )
    else:
        print(encoded, end="")
    if report["matched_count"] != report["selected_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
