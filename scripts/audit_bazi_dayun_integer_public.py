"""Separate actual old/new service processes and bound every integer-age change."""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import math
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.audit_bazi_dayun_integer import (
    FIXTURE,
    ROOT,
    digest,
    frozen,
    write_summary,
)


def collect_phase(phase: str) -> list[dict[str, Any]]:
    if phase == "legacy":
        sources = frozen(FIXTURE / "before-source.json.gz")
        sources.update(frozen(FIXTURE / "additional-source-before-repair.json.gz"))
        sources.update(frozen(FIXTURE / "overview-source-before-repair.json.gz"))
        for name in [
            "src/fatebridge/core/timing.py",
            "src/fatebridge/analysis/timing_effects.py",
            "src/fatebridge/services/timing_snapshots.py",
            "src/fatebridge/services/timing.py",
            "src/fatebridge/services/bazi.py",
        ]:
            module_name = (
                name.removeprefix("src/").removesuffix(".py").replace("/", ".")
            )
            parent = importlib.import_module(module_name.rsplit(".", 1)[0])
            module = types.ModuleType(module_name)
            module.__package__ = module_name.rsplit(".", 1)[0]
            module.__file__ = str(ROOT / name)
            sys.modules[module_name] = module
            setattr(parent, module_name.rsplit(".", 1)[1], module)
            exec(compile(sources[name], str(ROOT / name), "exec"), module.__dict__)
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG

    specs = {s.key: s for s in CATALOG}
    rows = []
    for row in frozen(FIXTURE / "public-baseline-first.json.gz")["rows"]:
        spec = specs[row["tool"]]
        result = execute_tool(
            spec,
            spec.request_model.model_validate(row["arguments"]),
            options=ExecutionOptions(as_of="2038-10-23T04:00:00Z"),
            include_metadata=False,
        )
        if "error" in result:
            raise ValueError("Actual " + phase + "service failed: " + row["tool"])
        rows.append(
            {k: v for k, v in row.items() if k not in {"result", "is_error"}}
            | {"result": result}
        )
    return rows


def compare(
    old: Any,
    new: Any,
    path: tuple[str, ...] = (),
    parents: tuple[Any, Any] = (None, None),
) -> list[dict[str, Any]]:
    changes = []
    if isinstance(old, dict) and isinstance(new, dict):
        if set(old) - set(new):
            raise ValueError("An original field disappeared: " + ".".join(path))
        for k in set(new) - set(old):
            overview = path == ("bazi_birth", "timing_overview", "dayun")
            if not (
                (k == "start_age_unrounded" and "start_age_precise" in old)
                or (overview and k in {"start_age_precise", "start_age_unrounded"})
            ):
                raise ValueError("Undeclared new field: " + ".".join((*path, k)))
            if round(new["start_age_unrounded"], 2) != new["start_age_precise"]:
                raise ValueError("Raw age differs from same display")
            changes.append(
                {
                    "path": ".".join((*path, k)),
                    "kind": (
                        "new_unrounded_age"
                        if k == "start_age_unrounded"
                        else "new_two_decimal_display"
                    ),
                    "new": new[k],
                }
            )
        for key in old:
            if key in {"snapshot_text", "snapshot_export"}:
                continue
            changes.extend(compare(old[key], new[key], (*path, key), (old, new)))
    elif isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            raise ValueError("An original list changed length: " + ".".join(path))
        for i, (a, b) in enumerate(zip(old, new, strict=True)):
            changes.extend(compare(a, b, (*path, str(i))))
    elif old != new:
        a, b = parents
        if (
            path[-1] == "start_age_rounded"
            and isinstance(a, dict)
            and "start_age_unrounded" in a
        ):
            expected = max(1, math.ceil(a["start_age_unrounded"]))
        elif (
            path[-1] == "start_age"
            and isinstance(a, dict)
            and (
                "start_age_precise" in a
                or path[:-1] == ("bazi_birth", "timing_overview", "dayun")
            )
            and "start_age_unrounded" in b
        ):
            expected = max(1, math.ceil(b["start_age_unrounded"]))
        else:
            raise ValueError("Unrelated actual business changed: " + ".".join(path))
        if new != expected or old != max(
            1, math.ceil(a.get("start_age_precise", b["start_age_precise"]))
        ):
            raise ValueError("Integer change differs from declared raw ceiling")
        changes.append(
            {
                "path": ".".join(path),
                "kind": "corrected_integer_age",
                "old": old,
                "new": new,
            }
        )
    return changes


def audit() -> dict[str, Any]:
    phases = {}
    for phase in ["legacy", "current"]:
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.audit_bazi_dayun_integer_public",
                "--phase",
                phase,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        phases[phase] = json.loads(done.stdout)
    if len(phases["legacy"]) != 72 or len(phases["current"]) != 72:
        raise ValueError("Missing declared actual entry profile")
    rows = []
    for a, b in zip(phases["legacy"], phases["current"], strict=True):
        if {k: v for k, v in a.items() if k != "result"} != {
            k: v for k, v in b.items() if k != "result"
        }:
            raise ValueError("Inputs or ordering changed")
        changes = compare(a["result"], b["result"])
        before = a["result"].get("snapshot_text", "")
        after = b["result"].get("snapshot_text", "")
        text_diff = (
            list(
                difflib.unified_diff(
                    before.splitlines(),
                    after.splitlines(),
                    fromfile="old_snapshot",
                    tofile="current_snapshot",
                    lineterm="",
                )
            )
            if before != after
            else []
        )
        rows.append(
            {
                "tool": a["tool"],
                "zone": a["zone"],
                "solar": a["solar"],
                "structured_changes": changes,
                "snapshot_diff": text_diff,
                "raw_snapshot_and_export_retained_in_phases": True,
            }
        )
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "runner_sha256": digest(Path(__file__)),
        "baseline_sha256": digest(FIXTURE / "public-baseline-first.json.gz"),
        "phase_scope": "Five frozen old timing/calculation/rendering modules versus current modules, using same then-current remaining dependencies and domain helpers in separate processes. Not full historical environment identity.",
        "phases": phases,
        "record_count": 72,
        "tools": 18,
        "changes": rows,
        "unapproved_structured_changes": 0,
        "existing_periods_boundary_instants_stars_and_strength_values_unchanged": True,
        "new_model_executions": 0,
        "new_classical_correct_cases_credited": 0,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["legacy", "current"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase:
        print(
            json.dumps(
                collect_phase(args.phase), ensure_ascii=False, separators=(",", ":")
            )
        )
        return
    if args.output is None or args.output.exists():
        parser.error("Choose a fresh output path")
    result = audit()
    write_summary(args.output, result)
    print(
        json.dumps(
            {
                "records": 72,
                "tools": 18,
                "changed_records": sum(
                    bool(r["structured_changes"]) for r in result["changes"]
                ),
                "unapproved_structured_changes": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
