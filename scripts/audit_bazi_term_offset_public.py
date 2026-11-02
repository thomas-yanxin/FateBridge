"""Compare ten full public payloads in separate old/new serialization processes."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.audit_bazi_term_offset_repair import DISCOVERY, NEW_FIELDS
from scripts.audit_bazi_term_offsets import ROOT, baseline_class, digest

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
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.almanac import SolarTerm
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG

    specs = {s.key: s for s in CATALOG}
    representative = json.loads(gzip.decompress(DISCOVERY.read_bytes()))[
        "representative"
    ]
    birth = datetime.fromisoformat(representative["actual_local_datetime"]).replace(
        tzinfo=None, hour=12, minute=0, second=0, microsecond=0
    ) - timedelta(days=2)
    arguments = dict(
        birth_year=birth.year,
        birth_month=birth.month,
        birth_day=birth.day,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=representative["zone"],
        gender="男",
        use_true_solar_time=False,
    )
    old, _ = baseline_class()
    serializer = old.as_dict if phase == "legacy" else SolarTerm.as_dict
    results = {}
    with patch.object(SolarTerm, "as_dict", serializer):
        for topic in TOPICS:
            spec = specs["bazi_" + topic]
            request = spec.request_model.model_validate(arguments)
            value = execute_tool(
                spec,
                request,
                options=ExecutionOptions(as_of=AS_OF),
                include_metadata=False,
            )
            if "error" in value or "error_code" in value:
                raise ValueError("Public execution failed: " + spec.key)
            if spec.output_model is None:
                raise ValueError("Public output model missing: " + spec.key)
            spec.output_model.model_validate(value)
            results[spec.key] = value
    return dict(arguments=arguments, as_of=AS_OF, payloads=results)


def compare(before: Any, after: Any, path: str, additions: list[str]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        extra = set(after) - set(before)
        if extra:
            if extra != NEW_FIELDS or not {
                "name",
                "datetime",
                "date_key",
                "day_ganzhi",
                "resolution_provider",
                "ephemeris_model",
            } <= set(before):
                raise ValueError("Unexpected added fields at " + path)
            additions.append(path)
        if set(before) - set(after):
            raise ValueError("Original field removed at " + path)
        for key in before:
            compare(before[key], after[key], path + "/" + key, additions)
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            raise ValueError("Original list length changed at " + path)
        for index, (old, new) in enumerate(zip(before, after)):
            compare(old, new, path + "/" + str(index), additions)
    elif type(before) is not type(after) or before != after:
        raise ValueError("Original value changed at " + path)


def audit() -> dict[str, Any]:
    source_paths = [
        "scripts/audit_bazi_term_offsets.py",
        "scripts/audit_bazi_term_offset_repair.py",
        "scripts/audit_bazi_term_offset_public.py",
        "src/fatebridge/core/almanac.py",
        "src/fatebridge/core/output_chinese.py",
        "uv.lock",
    ]
    source_hashes = {name: digest(ROOT / name) for name in source_paths}
    with tempfile.TemporaryDirectory(prefix="bazi-term-public-") as name:
        directory = Path(name)
        environment = dict(
            os.environ,
            SE_EPHE_PATH=str(directory),
            FATEBRIDGE_SOLAR_TERM_MODEL="auto",
            PYTHONPATH=str(ROOT),
        )
        environment.pop("FATEBRIDGE_JPL_FILE", None)
        phases = {}
        for phase in ("legacy", "current"):
            target = directory / (phase + ".json.gz")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.audit_bazi_term_offset_public",
                    "--phase",
                    phase,
                    "--output",
                    str(target),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            phases[phase] = json.loads(gzip.decompress(target.read_bytes()))
    additions: list[str] = []
    compare(phases["legacy"], phases["current"], "", additions)
    if not additions:
        raise ValueError("No aware facts reached the public payloads")
    if source_hashes != {name: digest(ROOT / name) for name in source_paths}:
        raise ValueError("Compared source changed during public execution")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_sources_sha256=source_hashes,
        first_discovery_sha256=digest(DISCOVERY),
        phases=phases,
        solar_term_records_enriched=len(additions),
        enriched_paths=additions,
        all_original_public_values_identical=True,
        separate_processes=True,
        comparison_scope="Same current dependencies with frozen original SolarTerm serializer versus current serializer, not the whole original backend; actual full business payloads, including text, timing and strength values, retained.",
        model_executions=0,
        source_force_adjudication="not_completed",
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
        raise SystemExit("Preserve existing results")
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
                {
                    k: result[k]
                    for k in (
                        "solar_term_records_enriched",
                        "all_original_public_values_identical",
                        "separate_processes",
                        "full_goal_complete",
                    )
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
