"""Reproduce the unchanged four isolated natal source-consistency controls."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

from fatebridge.core.astro import runtime
from fatebridge.services.human_design import calculate_human_design

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-natal-source-plan.json"


@contextmanager
def isolated_source_change(kind: str, directory: Path) -> Iterator[dict[str, Any]]:
    if kind not in {"file_bytes", "temporary_path", "slot_edition", "late_file_bytes"}:
        raise ValueError("Unknown frozen source probe")
    private = directory / "ephe"
    private.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(ROOT / "ephe" / name, private / name)
        (private / name).chmod(0o644)
    other = directory / "other"
    if kind == "temporary_path":
        shutil.copytree(private, other)
    original = runtime.ephemeris_call
    getter = runtime.swe.get_current_file_data
    state: dict[str, Any] = {"native_sun_calls": 0, "mutation_performed": False}

    def native(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == 0:
            state["native_sun_calls"] += 1
            count = state["native_sun_calls"]
            if (
                kind == "late_file_bytes"
                and args[2] & 7 == 4
                and not state["mutation_performed"]
            ):
                state["mutation_performed"] = True
                with (private / "sepl_18.se1").open("ab") as handle:
                    handle.write(b"late-natal-source-change-regression")
            if count == 2 and kind != "late_file_bytes":
                state["mutation_performed"] = True
                if kind == "file_bytes":
                    with (private / "sepl_18.se1").open("ab") as handle:
                        handle.write(b"natal-source-change-regression")
                elif kind == "temporary_path":
                    os.environ["SE_EPHE_PATH"] = str(other)
            if kind == "temporary_path" and count == 3:
                os.environ["SE_EPHE_PATH"] = str(private)
        return result

    def metadata(slot):
        row = getter(slot)
        if (
            kind == "slot_edition"
            and slot == 0
            and state["native_sun_calls"] >= 2
            and row[0]
        ):
            return (*row[:3], row[3] + 1)
        return row

    with (
        patch.dict(os.environ, {"SE_EPHE_PATH": str(private)}),
        patch.object(runtime, "ephemeris_call", native),
        patch.object(runtime.swe, "get_current_file_data", metadata),
    ):
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
        yield state


def regression_checks() -> dict[str, Any]:
    from fatebridge.core.astro.native_execution import in_native_worker

    if not in_native_worker():
        worker = ROOT / "scripts/human_design/human_design_source_fault_worker.py"
        done = subprocess.run(
            [sys.executable, "-I", str(worker)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if done.returncode:
            raise RuntimeError("Controlled Human Design native fault worker failed")
        return json.loads(done.stdout)
    plan = json.loads(PLAN_PATH.read_text())
    if len(plan["cases"]) != 4:
        raise ValueError("Incomplete source controls")
    cases = []
    for case in plan["cases"]:
        with tempfile.TemporaryDirectory(
            prefix="hd-natal-file-acceptance-"
        ) as directory:
            with isolated_source_change(case["id"], Path(directory)) as state:
                result = calculate_human_design(**plan["birth_input"])
                safe = str(directory) not in json.dumps(result)
                passed = (
                    state["mutation_performed"]
                    and result.get("error_code") == case["expected_error_code"]
                    and result.get("retryable") is False
                    and safe
                )
                cases.append(
                    {
                        "id": case["id"],
                        **state,
                        "error_code": result.get("error_code"),
                        "issues": result.get("issues"),
                        "private_paths_absent": safe,
                        "passed": passed,
                    }
                )
    return {
        "method_id": "human_design_natal_source_regression_v1",
        "status": (
            "bounded_natal_source_checks_passed"
            if all(c["passed"] for c in cases)
            else "failed"
        ),
        "cases": cases,
        "scope": "Three previously accepted source inconsistencies plus the original native damaged-file rejection retained. Safe source errors under private file/path/metadata mutations. No new independent celestial accuracy, atomic-read, full source-prose or live-model certification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = regression_checks()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if result["status"] == "bounded_natal_source_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
