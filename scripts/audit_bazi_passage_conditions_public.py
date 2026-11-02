"""Compare complete actual outputs under frozen old/current passage contracts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_passage_conditions_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payloads(phase: str) -> dict[str, Any]:
    if phase == "legacy":
        before = json.loads(
            gzip.decompress((FIXTURE / "before-source.json.gz").read_bytes())
        )
        name = "fatebridge.core.output_classical_passage"
        module = types.ModuleType(name)
        sys.modules[name] = module
        exec(
            compile(
                before["src/fatebridge/core/output_classical_passage.py"],
                "pre_passage_contract.py",
                "exec",
            ),
            module.__dict__,
        )
        setattr(
            importlib.import_module("fatebridge.core"),
            "output_classical_passage",
            module,
        )
    from fatebridge.services.tool_catalog import CATALOG
    from scripts.audit_bazi_month_duty_scan_public import payloads as actual_payloads

    value = actual_payloads("current")
    specs = {s.key: s for s in CATALOG}
    schemas = {}
    for name in value["payloads"]:
        model = specs[name].output_model
        if model is None:
            raise ValueError("A public BaZi tool lacks its output contract: " + name)
        schemas[name] = hashlib.sha256(
            json.dumps(
                model.model_json_schema(), ensure_ascii=False, sort_keys=True
            ).encode()
        ).hexdigest()
    value["output_schema_sha256"] = schemas
    return value


def audit() -> dict[str, Any]:
    names = [
        "scripts/audit_bazi_passage_conditions_public.py",
        "scripts/audit_bazi_month_duty_scan_public.py",
        "src/fatebridge/core/output_classical_passage.py",
        "src/fatebridge/core/classical_passage.py",
        "src/fatebridge/core/output_bazi_evidence.py",
        "src/fatebridge/core/bazi_evidence.py",
        "src/fatebridge/core/strength.py",
        "uv.lock",
    ]
    before = {n: digest(ROOT / n) for n in names}
    phases = {}
    with tempfile.TemporaryDirectory(prefix="bazi-passage-contract-") as directory:
        env = dict(
            os.environ,
            SE_EPHE_PATH=directory,
            FATEBRIDGE_SOLAR_TERM_MODEL="auto",
            PYTHONPATH=str(ROOT),
        )
        env.pop("FATEBRIDGE_JPL_FILE", None)
        for phase in ("legacy", "current"):
            path = Path(directory) / (phase + ".json.gz")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_bazi_passage_conditions_public",
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
            phases[phase] = json.loads(gzip.decompress(path.read_bytes()))
    if phases["legacy"] != phases["current"]:
        raise ValueError(
            "A valid business output or output schema changed under the contract repair"
        )
    if before != {n: digest(ROOT / n) for n in names}:
        raise ValueError("A selected execution source changed during comparison")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_sources_sha256=before,
        phases=phases,
        actual_tools=len(phases["current"]["payloads"]),
        separate_old_new_processes=True,
        all_valid_full_business_values_text_and_schemas_identical=True,
        scope="Same current dependencies and business code; frozen old passage output validator versus current validator. Not the entire historical runtime, independent classic conformity, actual model or real-prediction acceptance.",
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
    value = payloads(args.phase) if args.phase else audit()
    data = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(data, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                phase=args.phase,
                tools=(
                    len(value.get("payloads", {}))
                    if args.phase
                    else value["actual_tools"]
                ),
                valid_outputs_identical=value.get(
                    "all_valid_full_business_values_text_and_schemas_identical"
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
