"""Keep first absence faults and verify full versus partial BaZi contracts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import types
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fatebridge.application.execution import OutputContractError, validate_output
from fatebridge.core.output_bazi_anchors import BAZI_ANCHOR_TOOLS
from fatebridge.services.tool_catalog import CATALOG

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_complete_anchors_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def frozen(path: Path) -> Any:
    if digest(path) != Path(str(path) + ".sha256").read_text().strip():
        raise ValueError("Frozen complete-output evidence changed: " + str(path))
    return read(path)


def legacy_validator() -> Any:
    before = frozen(FIXTURE / "before-source.json.gz")
    name = "_frozen_pre_bazi_complete_execution"
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(
        compile(
            before["src/fatebridge/application/execution.py"],
            "pre_complete_execution.py",
            "exec",
        ),
        module.__dict__,
    )
    return module.__dict__["validate_output"]


def audit() -> dict[str, Any]:
    protocol = frozen(FIXTURE / "protocol.json")
    before = frozen(FIXTURE / "before-source.json.gz")
    baseline = frozen(FIXTURE / "baseline-first.json.gz")
    first = frozen(FIXTURE / "counterexamples-first.json.gz")
    if digest(FIXTURE / "before-source.json.gz") != protocol["before_source_sha256"]:
        raise ValueError("Original execution archive changed")
    for name, expected in protocol["preserved_references_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Original counterexample, label or gate changed")
    preserved = [
        n
        for n in before
        if n
        not in {
            "src/fatebridge/application/execution.py",
            "docs/validation/bazi-three-axis-requirements.json",
            "uv.lock",
        }
    ]
    for name in preserved:
        if (ROOT / name).read_text() != before[name]:
            raise ValueError("A preserved producer or partial schema changed: " + name)
    specs = {s.key: s for s in CATALOG}
    if set(baseline["tools"]) != BAZI_ANCHOR_TOOLS:
        raise ValueError("Public BaZi entry coverage changed")
    old = legacy_validator()
    rows = []
    for row in baseline["rows"]:
        if row["is_error"]:
            raise ValueError("A baseline branch already failed")
        payload = deepcopy(row["result"])
        old(specs[row["tool"]], payload)
        validate_output(specs[row["tool"]], payload)
        if payload != row["result"]:
            raise ValueError("Validation altered a valid business value")
        rows.append(
            dict(
                tool=row["tool"],
                variant=row["variant"],
                full_original_result_unchanged=True,
            )
        )
    faults = []
    for case in first["controls"]:
        old(specs[case["tool"]], case["payload"])
        try:
            validate_output(specs[case["tool"]], case["payload"])
        except OutputContractError as exc:
            message = str(exc)
        else:
            raise ValueError(
                "A first absence control still passes: "
                + case["tool"]
                + "/"
                + case["kind"]
            )
        faults.append(
            dict(
                tool=case["tool"],
                kind=case["kind"],
                path=case["path"],
                old_accepted=True,
                current_rejected=True,
                error=message,
            )
        )
    for key in BAZI_ANCHOR_TOOLS:
        model = specs[key].output_model
        if model is None:
            raise ValueError("A public BaZi schema is missing")
        model.model_validate({})
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        runner_sha256=digest(Path(__file__)),
        protocol_sha256=digest(FIXTURE / "protocol.json"),
        required_full_guard_sha256=digest(
            ROOT / "src/fatebridge/core/output_bazi_anchors.py"
        ),
        shared_execution_sha256=digest(
            ROOT / "src/fatebridge/application/execution.py"
        ),
        scope=protocol["scope"],
        public_tools=list(baseline["tools"]),
        valid_original_branches=rows,
        valid_record_count=len(rows),
        first_absence_control_results=faults,
        artificial_fault_count=len(faults),
        observed_production_missing_anchor_outputs_in_initial86=0,
        all_partial_models_remain_readable=True,
        preserved_files=preserved,
        original_nineteen_relabelled=False,
        new_numeric_calculation_repairs=0,
        new_classical_correct_cases_credited=0,
        new_model_executions=0,
        new_actual_model_explanation_acceptance="not_tested",
        independent_expert_acceptance="not_completed",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first results; choose a new path")
    result = audit()
    raw = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(raw, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                tools=len(result["public_tools"]),
                valid_records=result["valid_record_count"],
                artificial_faults_rejected=result["artificial_fault_count"],
            )
        )
    )


if __name__ == "__main__":
    main()
