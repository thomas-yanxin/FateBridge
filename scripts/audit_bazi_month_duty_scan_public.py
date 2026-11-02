"""Compare complete ten-tool business payloads with old/new month-source delivery."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast
from unittest.mock import patch

from scripts.audit_bazi_month_duty_scan import FIXTURE, ROOT, digest

TOPICS = (
    "birth",
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
)
AS_OF = "2026-10-12T02:00:00Z"


def payloads(phase: str) -> dict[str, Any]:
    import fatebridge.core.bazi_evidence as evidence
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG

    before = json.loads(
        gzip.decompress((FIXTURE / "before-source.json.gz").read_bytes())
    )
    legacy = types.ModuleType("_frozen_pre_scan_month_reference")
    exec(
        compile(
            before["src/fatebridge/core/month_duty_reference.py"],
            "pre_scan_month_reference.py",
            "exec",
        ),
        legacy.__dict__,
    )
    old = cast(
        Callable[..., dict[str, Any]], legacy.__dict__["build_month_duty_reference"]
    )
    selected = old if phase == "legacy" else evidence.build_month_duty_reference
    arguments = dict(
        birth_year=1990,
        birth_month=2,
        birth_day=15,
        birth_hour=10,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    specs = {s.key: s for s in CATALOG}
    results = {}
    with patch.object(evidence, "build_month_duty_reference", selected):
        for topic in TOPICS:
            spec = specs["bazi_" + topic]
            result = execute_tool(
                spec,
                spec.request_model.model_validate(arguments),
                options=ExecutionOptions(as_of=AS_OF),
                include_metadata=False,
            )
            if spec.output_model is None or "error" in result or "error_code" in result:
                raise ValueError(
                    "Tool execution or output contract failed: " + spec.key
                )
            spec.output_model.model_validate(result)
            results[spec.key] = result
    return dict(arguments=arguments, as_of=AS_OF, payloads=results)


def compare(before: Any, current: Any, path: str, additions: list[str]) -> None:
    if isinstance(before, dict) and isinstance(current, dict):
        extra = current.keys() - before.keys()
        if extra:
            if (
                extra != {"scanned_witness"}
                or not {
                    "method_id",
                    "duration_source_layers",
                    "effective_command_status",
                    "calculation_effect",
                }
                <= before.keys()
            ):
                raise ValueError("Unexpected added fields at " + path)
            additions.append(path + "/scanned_witness")
        if before.keys() - current.keys():
            raise ValueError("Old field removed at " + path)
        for key in before:
            compare(before[key], current[key], path + "/" + key, additions)
    elif isinstance(before, list) and isinstance(current, list):
        if len(before) != len(current):
            raise ValueError("Old list length changed at " + path)
        for index, (old, new) in enumerate(zip(before, current)):
            compare(old, new, path + "/" + str(index), additions)
    elif type(before) is not type(current) or before != current:
        raise ValueError("Old business value changed at " + path)


def audit() -> dict[str, Any]:
    paths = [
        "scripts/audit_bazi_month_duty_scan_public.py",
        "src/fatebridge/core/month_duty_reference.py",
        "src/fatebridge/core/month_duty_scan_reference.py",
        "src/fatebridge/data/bazi_month_duty_sources_v1.json",
        "src/fatebridge/data/bazi_month_duty_scan_v1.json",
        "uv.lock",
    ]
    fingerprints = {name: digest(ROOT / name) for name in paths}
    phases = {}
    with tempfile.TemporaryDirectory(prefix="bazi-scan-public-") as directory:
        environment = dict(
            os.environ,
            SE_EPHE_PATH=directory,
            FATEBRIDGE_SOLAR_TERM_MODEL="auto",
            PYTHONPATH=str(ROOT),
        )
        environment.pop("FATEBRIDGE_JPL_FILE", None)
        for phase in ("legacy", "current"):
            output = Path(directory) / (phase + ".json.gz")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_bazi_month_duty_scan_public",
                    "--phase",
                    phase,
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            phases[phase] = json.loads(gzip.decompress(output.read_bytes()))
    additions: list[str] = []
    compare(phases["legacy"], phases["current"], "", additions)
    if len(additions) != 10:
        raise ValueError("The new witness must reach all ten actual business payloads")
    if fingerprints != {name: digest(ROOT / name) for name in paths}:
        raise ValueError("Compared source changed during execution")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_sources_sha256=fingerprints,
        phases=phases,
        enriched_paths=additions,
        all_original_full_business_values_and_text_identical=True,
        separate_old_new_processes=True,
        comparison_scope="Same current dependencies with frozen original month-source builder versus current builder; not the whole original runtime or an independent prediction trial.",
        new_model_executions=0,
        effective_month_duty="not_adjudicated",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("legacy", "current"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or Path(str(output) + ".sha256").exists():
        raise SystemExit("Preserve first results")
    result = payloads(args.phase) if args.phase else audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    Path(str(output) + ".sha256").write_text(digest(output) + "\n")
    if not args.phase:
        print(
            json.dumps(
                dict(
                    enriched_objects=len(result["enriched_paths"]),
                    all_old_values_identical=result[
                        "all_original_full_business_values_and_text_identical"
                    ],
                    full_goal_complete=False,
                )
            )
        )


if __name__ == "__main__":
    main()
