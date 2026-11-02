"""Compare all11 valid business outputs under frozen old/current full guards."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.audit_bazi_complete_anchors import (
    FIXTURE,
    ROOT,
    digest,
    legacy_validator,
    read,
)


def payloads(phase: str) -> dict[str, Any]:
    import fatebridge.application.execution as execution
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG

    specs = {s.key: s for s in CATALOG}
    rows = read(FIXTURE / "baseline-first.json.gz")["rows"]
    selected = legacy_validator() if phase == "legacy" else execution.validate_output
    values = {}
    schemas = {}
    arguments = {}
    with patch.object(execution, "validate_output", selected):
        for row in rows:
            if row["variant"] != "base":
                continue
            spec = specs[row["tool"]]
            model = spec.output_model
            if model is None:
                raise ValueError("A public output model is missing")
            value = execution.execute_tool(
                spec,
                spec.request_model.model_validate(row["arguments"]),
                options=ExecutionOptions(as_of="2026-10-12T02:00:00Z"),
                include_metadata=False,
            )
            if "error" in value:
                raise ValueError("A valid producer failed: " + spec.key)
            model.model_validate(value)
            values[spec.key] = value
            arguments[spec.key] = row["arguments"]
            schemas[spec.key] = model.model_json_schema()
    return dict(
        arguments=arguments,
        payloads=values,
        output_schemas=schemas,
        as_of="2026-10-12T02:00:00Z",
    )


def audit() -> dict[str, Any]:
    names = [
        "scripts/audit_bazi_complete_anchors_public.py",
        "scripts/audit_bazi_complete_anchors.py",
        "src/fatebridge/application/execution.py",
        "src/fatebridge/core/output_bazi_anchors.py",
        "src/fatebridge/core/bazi_evidence.py",
        "src/fatebridge/core/strength.py",
        "src/fatebridge/services/bazi.py",
        "src/fatebridge/services/birth_payload.py",
        "uv.lock",
    ]
    hashes = {n: digest(ROOT / n) for n in names}
    phases = {}
    with tempfile.TemporaryDirectory(prefix="bazi-complete-output-") as directory:
        env = dict(
            os.environ,
            PYTHONPATH=str(ROOT),
            SE_EPHE_PATH=directory,
            FATEBRIDGE_SOLAR_TERM_MODEL="auto",
        )
        env.pop("FATEBRIDGE_JPL_FILE", None)
        for phase in ("legacy", "current"):
            path = Path(directory) / (phase + ".json.gz")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_bazi_complete_anchors_public",
                    "--phase",
                    phase,
                    "--output",
                    str(path),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            phases[phase] = read(path)
    if phases["legacy"] != phases["current"]:
        raise ValueError("A valid complete business value or partial schema changed")
    if hashes != {n: digest(ROOT / n) for n in names}:
        raise ValueError("A selected source changed during comparison")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_sources_sha256=hashes,
        phases=phases,
        actual_tools=len(phases["current"]["payloads"]),
        all_original_complete_business_values_text_and_partial_schemas_identical=True,
        separate_old_new_processes=True,
        scope="Same current dependencies/producers, frozen original full-output validator versus current full-output validator. Includes actual analyze_destiny comprehensive entry. Not the whole historical runtime or an independent model/prediction trial.",
        new_model_executions=0,
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("legacy", "current"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first outputs; choose a new path")
    result = payloads(args.phase) if args.phase else audit()
    raw = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(raw, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                phase=args.phase,
                tools=(
                    len(result.get("payloads", {}))
                    if args.phase
                    else result["actual_tools"]
                ),
                values_identical=result.get(
                    "all_original_complete_business_values_text_and_partial_schemas_identical"
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
