"""Replay every frozen valid/invalid request against fresh production workers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-cycle-input-plan.json"
BEFORE = ROOT / "docs/validation/human-design-cycle-input-before.json"
ORDINARY = ROOT / "docs/validation/human-design-ordinary-clock-before.json"


def regression_checks() -> dict:
    if (
        hashlib.sha256(PLAN.read_bytes()).hexdigest()
        != "a790ca39da2576edeffbbbb19646160b8f2ff1937b2015f31eeb2a852bcd42cd"
        or hashlib.sha256(BEFORE.read_bytes()).hexdigest()
        != "f676dbe6bd5adba9c36588a0febd9c571465388923757f564b7243507554d7b2"
    ):
        raise ValueError("Frozen request-clock evidence changed")
    plan = json.loads(PLAN.read_text())
    rows = []
    with tempfile.TemporaryDirectory(prefix="fatebridge-hd-request-") as directory:
        for empty in (False, True):
            env = {
                **os.environ,
                "SE_EPHE_PATH": directory if empty else str(ROOT / "ephe"),
            }
            env.pop("FATEBRIDGE_JPL_FILE", None)
            for case in plan["cases"]:
                for kind in plan["perturbations"]:
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            str(ROOT / "tests/human_design_cycle_input_driver.py"),
                            json.dumps(case["input"]),
                            kind,
                        ],
                        cwd=ROOT,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if completed.returncode:
                        raise RuntimeError(
                            "Frozen native request-clock regression failed"
                        )
                    result = json.loads(completed.stdout)
                    if (
                        result["input"] != case["input"]
                        or not result["parent_setting_preserved"]
                        or result["dirty"]["accepted"] != case["expected_accepted"]
                        or result["clean"]["accepted"] != case["expected_accepted"]
                    ):
                        raise ValueError(
                            "Request decision or caller-state invariant failed"
                        )
                    rows.append(
                        {
                            "id": case["id"],
                            "configured_backend": (
                                "empty_path_moshier" if empty else "packaged_swiss"
                            ),
                            "perturbation": kind,
                            "accepted": result["dirty"]["accepted"],
                            "parent_setting_preserved": True,
                        }
                    )
    return {
        "method_id": "human_design_native_request_clock_isolation_regression_v1",
        "status": "bounded_cycle_request_clock_isolation_passed",
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "before_sha256": hashlib.sha256(BEFORE.read_bytes()).hexdigest(),
        "cases": rows,
        "scope": "All6 original valid/invalid inputs, both original manual native perturbations, both Swiss/empty configurations. Correct clean1.27 decisions and caller state retained. Actual time ordering remains TT-based; no native parent reset, civil-sort substitution, dropped invalid case or relaxed physical tolerance. Not complete calendar or native authentication.",
    }


def ordinary_clock_checks() -> dict:
    """Keep the newly found ordinary-clock gap visible until it is repaired."""
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.replay_metadata import digest
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.human_design import verify_human_design_reading

    if (
        hashlib.sha256(ORDINARY.read_bytes()).hexdigest()
        != "5986043da4618391e9d6057f449068ea83ae39c6b07e0d50d7b6fdf18b8cf1a9"
    ):
        raise ValueError("Frozen ordinary-clock mutation cases changed")
    before = json.loads(ORDINARY.read_text())
    spec = next(s for s in CATALOG if s.key == "human_design")
    original = execute_tool(spec, spec.request_model(**before["input"]))
    control = verify_human_design_reading(original)
    if control["status"] != "verified_fixed_template_reading":
        raise ValueError(
            "Ordinary clock control must remain a valid complete run: "
            + json.dumps(control, ensure_ascii=False, sort_keys=True)
        )
    rows = []
    for case in before["mutations"]:
        p = deepcopy(original)
        parts = case["path"].split(".")
        target = p
        for key in parts[:-1]:
            target = target[key]
        if target[parts[-1]] == case["replacement"]:
            raise ValueError("No-op ordinary-clock probe")
        target[parts[-1]] = case["replacement"]
        p["run_metadata"]["business_output_sha256"] = digest(
            {k: v for k, v in p.items() if k != "run_metadata"}
        )
        check = verify_human_design_reading(p)
        rows.append(
            {"id": case["id"], "status": check["status"], "errors": check["errors"]}
        )
    from scripts.check_human_design_clock_replay import (
        regression_checks as clock_replay_checks,
    )

    expanded = clock_replay_checks()
    unresolved = [r["id"] for r in rows if r["status"] != "rejected"]
    unresolved.extend(expanded["unresolved"])
    if expanded["status"] != "passed" and not expanded["unresolved"]:
        unresolved.append("expanded_clock_positive_control")
    return {
        "method_id": "human_design_ordinary_civil_clock_fidelity_gap_v1",
        "status": "failed" if unresolved else "passed",
        "before_sha256": hashlib.sha256(ORDINARY.read_bytes()).hexdigest(),
        "control": control,
        "cases": rows,
        "unresolved": unresolved,
        "expanded_clock_replay": expanded,
        "scope": "All9 original rehashed mutations retained. Ordinary local-label/timezone/calendar policy, UT1, method and future-assumption fields require additional clock witnesses and consistency verification. Existing fixed-template acceptance is not an input-clock or native-execution authenticity certificate. Do not mark this complete because the separate request-isolation regression passed.",
    }


if __name__ == "__main__":
    print(
        json.dumps(
            {"request": regression_checks(), "ordinary": ordinary_clock_checks()},
            ensure_ascii=False,
            indent=2,
        )
    )
