"""Retain all frozen dirty-parent inputs across real production exec dispatch."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "docs/validation/human-design-native-state-before.json"
PLAN = ROOT / "tests/fixtures/human-design-native-state-plan.json"


def regression_checks() -> dict:
    before_sha = hashlib.sha256(BEFORE.read_bytes()).hexdigest()
    plan_sha = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    if (
        before_sha != "50c86b4334eee19b38533cbe905d17407021b9ad53c1d2a75be2cec9a7cfcf40"
        or plan_sha
        != "f008e248178721c9225c7f10b359b9596fc9a0692327cec7a791098223590522"
    ):
        raise ValueError("Frozen native-state evidence changed")
    plan = json.loads(PLAN.read_text())
    rows = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-hd-state-") as directory:
        for empty in (False, True):
            for birth in plan["mandatory_birth_inputs"]:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        str(ROOT / "tests/human_design_native_state_driver.py"),
                        str(birth["birth_year"]),
                        directory if empty else str(ROOT / "ephe"),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if completed.returncode:
                    raise RuntimeError("Frozen dirty-parent production check failed")
                row = json.loads(completed.stdout)
                if row["birth_input"] != birth or not all(
                    row[k] is True
                    for k in (
                        "complete_business_output_identical",
                        "parent_setting_preserved",
                        "full_readings_verified",
                    )
                ):
                    raise ValueError("Incomplete dirty-parent check")
                rows.append(
                    {
                        "configured_backend": (
                            "empty_path_moshier" if empty else "packaged_swiss"
                        ),
                        **row,
                    }
                )
    return {
        "method_id": "human_design_production_native_state_regression_v1",
        "status": "bounded_native_state_isolation_passed",
        "before_sha256": before_sha,
        "plan_sha256": plan_sha,
        "cases": rows,
        "scope": "All four frozen birth inputs, two configured file contexts, real fresh-process dispatch. Complete business dictionaries including all diagnostics compare exactly; independent run receipts are verified in full. Synthetic parent DeltaT=0.1days remains unchanged. This bounded test does not authenticate native execution, establish physical accuracy, resolve original sources, certify arbitrary prose, continuous dates or real-world prediction.",
    }


if __name__ == "__main__":
    print(json.dumps(regression_checks(), ensure_ascii=False, indent=2))
