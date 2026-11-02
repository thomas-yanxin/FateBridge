"""Compare ten complete business payloads before and after the identity layer."""

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

from scripts.audit_bazi_month_duty_identity import ROOT, digest, legacy_builders
from scripts.audit_bazi_month_duty_scan_public import payloads as scan_payloads


def payloads(phase: str) -> dict[str, Any]:
    import fatebridge.core.bazi_evidence as evidence

    _, old = legacy_builders()
    selected = old if phase == "legacy" else evidence.build_month_duty_reference
    with patch.object(evidence, "build_month_duty_reference", selected):
        return scan_payloads("current")


def compare(before: Any, current: Any, path: str, additions: list[str]) -> None:
    if isinstance(before, dict) and isinstance(current, dict):
        extra = current.keys() - before.keys()
        if extra:
            if extra != {"cross_chapter_identities"} or not path.endswith(
                "/scanned_witness"
            ):
                raise ValueError("Unexpected added business fields at " + path)
            additions.append(path + "/cross_chapter_identities")
        if before.keys() - current.keys():
            raise ValueError("An old field disappeared at " + path)
        for key in before:
            compare(before[key], current[key], path + "/" + key, additions)
    elif isinstance(before, list) and isinstance(current, list):
        if len(before) != len(current):
            raise ValueError("An old list length changed at " + path)
        for i, (a, b) in enumerate(zip(before, current, strict=True)):
            compare(a, b, path + "/" + str(i), additions)
    elif type(before) is not type(current) or before != current:
        raise ValueError("An old business value changed at " + path)


def audit() -> dict[str, Any]:
    names = [
        "scripts/audit_bazi_month_duty_identity_public.py",
        "scripts/audit_bazi_month_duty_identity.py",
        "scripts/audit_bazi_month_duty_scan_public.py",
        "src/fatebridge/core/month_duty_identity.py",
        "src/fatebridge/core/month_duty_scan_reference.py",
        "src/fatebridge/core/month_duty_reference.py",
        "src/fatebridge/data/bazi_month_duty_identity_v1.json",
        "src/fatebridge/data/bazi_month_duty_scan_v1.json",
        "src/fatebridge/data/bazi_month_duty_sources_v1.json",
        "uv.lock",
    ]
    fingerprints = {name: digest(ROOT / name) for name in names}
    phases = {}
    with tempfile.TemporaryDirectory(prefix="bazi-identity-public-") as directory:
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
                    "scripts.audit_bazi_month_duty_identity_public",
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
        raise ValueError("The identity layer must reach all ten tools")
    if fingerprints != {name: digest(ROOT / name) for name in names}:
        raise ValueError("A selected execution source changed during comparison")
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_sources_sha256=fingerprints,
        phases=phases,
        enriched_paths=additions,
        all_original_full_business_values_and_text_identical=True,
        separate_old_new_processes=True,
        comparison_scope="Same current dependencies; frozen pre-identity month builders versus current builders. Not the whole earlier runtime, new model behavior, independent text collation or real prediction.",
        new_model_executions=0,
        independent_expert_acceptance="not_completed",
        effective_month_duty="not_adjudicated",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("legacy", "current"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first results; choose a new output path")
    result = payloads(args.phase) if args.phase else audit()
    encoded = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(gzip.compress(encoded, mtime=0))
    Path(str(args.output) + ".sha256").write_text(digest(args.output) + "\n")
    print(
        json.dumps(
            dict(
                phase=args.phase,
                tools=len(result.get("payloads", result.get("enriched_paths", []))),
                old_values_identical=result.get(
                    "all_original_full_business_values_and_text_identical"
                ),
            )
        )
    )


if __name__ == "__main__":
    main()
