"""Independent C reference with explicit transitions over a guarded window.

No production clock reader is imported. All old point identities survive; the
old reference and its failed comparisons remain independent historical files.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.gen_human_design_timezone_history import (
    compact_initial,
    read,
    sha,
    transition_rows,
    write,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-timezone-window-v1"
E = BASE / "evidence"
OLD = ROOT / "docs/validation/human-design-timezone-history-v1"
PLAN_SHA = "71949acc391d70ea2097592438cb84bec672cf062fdd0f95bc8ce1c62d4a9b2b"


def inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    if sha(E / "plan.json") != PLAN_SHA:
        raise ValueError("Frozen explicit-window plan changed")
    plan = read(E / "plan.json")
    for name, expected in plan["input_bindings"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Frozen history input changed: " + name)
    for name, fact in plan["toolchain"].items():
        if sha(Path(name)) != fact["sha256"]:
            raise ValueError("Frozen C tool identity changed")
    old = read(OLD / "evidence/independent-reference.json.gz")
    if old["zone_count"] != 597 or len(old["anchor_seconds_since1970"]) != 1200:
        raise ValueError("Old original corpus incomplete")
    return plan, old


def build(output: Path) -> None:
    if output.exists():
        raise FileExistsError(output)
    if any(n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules):
        raise ValueError("Independent builder imported the production package")
    plan, old = inputs()
    low, high = plan["lower_guard_seconds"], plan["upper_guard_seconds"]
    if (low, high) != (-5396198400, 13601088000):
        raise ValueError("Guard bands or supported horizon changed")
    first, second = (
        old["forms"][name]["zones"] for name in ("primary", "full_backzone")
    )
    if [z["name"] for z in first] != [z["name"] for z in second]:
        raise ValueError("Original source forms have different names")
    inherited = []
    for a, b in zip(first, second, strict=True):
        points = sorted(
            {
                -5364662400,
                13569465599,
                *old["anchor_seconds_since1970"],
                *(r[0] for r in a["boundary_observations"]),
                *(r[0] for r in b["boundary_observations"]),
            }
        )
        if not all(low <= t < high for t in points):
            raise ValueError("An original point falls outside the explicit guard")
        inherited.append({"name": a["name"], "utc_seconds_since1970": points})
    if (
        len(inherited) != 597
        or sum(len(z["utc_seconds_since1970"]) for z in inherited) != 1071960
    ):
        raise ValueError("An old original point was omitted")
    forms: dict[str, dict[str, Any]] = {}
    environment = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    for form in ("primary", "full_backzone"):
        source = OLD / "sources" / (form + ".zi")
        destination = BASE / "reference-data" / form
        destination.mkdir(parents=True)
        command = [
            "/usr/sbin/zic",
            "-b",
            "fat",
            "-r",
            f"@{low}/@{high}",
            "-d",
            str(destination),
            str(source),
        ]
        compiled = subprocess.run(
            command, env=environment, capture_output=True, text=True
        )
        write(
            E / ("compile-" + form + ".json"),
            {
                "command": command,
                "source_sha256": sha(source),
                "exit_code": compiled.returncode,
                "stdout": compiled.stdout,
                "stderr": compiled.stderr,
            },
        )
        compiled.check_returncode()
        zones: list[dict[str, Any]] = []
        raw_outputs: list[dict[str, Any]] = []
        for index, previous in enumerate(old["forms"][form]["zones"]):
            path = destination / previous["name"]
            verbose = subprocess.run(
                ["/usr/sbin/zdump", "-V", "-c", "1800,2400", str(path)],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            compact = subprocess.run(
                ["/usr/sbin/zdump", "-i", "-c", "1800,1801", str(path)],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            if verbose.stderr or compact.stderr:
                raise ValueError("Unexpected C reference observer warning")
            zones.append(
                {
                    "name": previous["name"],
                    "compiled_tzif_sha256": sha(path),
                    "initial": compact_initial(compact.stdout),
                    "boundary_observations": transition_rows(verbose.stdout, path),
                }
            )
            raw_outputs.append(
                {
                    "name": previous["name"],
                    "verbose": verbose.stdout,
                    "initial_compact": compact.stdout,
                }
            )
            if (index + 1) % 100 == 0:
                print(form, index + 1, flush=True)
        write(E / ("raw-zdump-" + form + ".json.gz"), raw_outputs)
        forms[form] = {
            "zones": zones,
            "boundary_observation_count": sum(
                len(z["boundary_observations"]) for z in zones
            ),
            "all_compiled_files": {
                str(p.relative_to(destination)): sha(p)
                for p in sorted(destination.rglob("*"))
                if p.is_file()
            },
        }
    inputs()
    if any(n == "fatebridge" or n.startswith("fatebridge.") for n in sys.modules):
        raise ValueError("Independent builder used a production module")
    result = {
        "method_id": "human_design_guarded_explicit_C_timezone_reference_v1",
        "plan_sha256": PLAN_SHA,
        "inherited_reference_sha256": sha(
            OLD / "evidence/independent-reference.json.gz"
        ),
        "generator_sha256": sha(Path(__file__)),
        "parser_module_sha256": sha(
            ROOT / "scripts/gen_human_design_timezone_history.py"
        ),
        "toolchain": plan["toolchain"],
        "lower_guard_seconds": low,
        "upper_guard_seconds_exclusive": high,
        "query_year_range": [1800, 2400],
        "zone_count": 597,
        "inherited_point_count": 1071960,
        "inherited_points": inherited,
        "anchor_seconds_since1970": old["anchor_seconds_since1970"],
        "boundary_columns": old["boundary_columns"],
        "forms": forms,
        "production_package_imported": False,
        "producer_numerical_values_used": False,
        "new_blind_or_independent_population_sample": False,
        "historical_truth_certified": False,
        "astronomical_accuracy_certified": False,
        "scope": "Same original IANA2026e guarded source and C2022g binary; only explicit1799..2401 representation changes. C observations cover1800..2399 with every old point retained for later comparison. Backzone remains fallible and separate. This does not overwrite earlier1086 mismatches, repair the old literal GMT criterion, authenticate clocks, or certify continuous astronomical accuracy.",
    }
    write(output, result)
    print(
        {
            "zones": 597,
            "inherited_points": 1071960,
            "boundary_rows": {
                k: v["boundary_observation_count"] for k, v in forms.items()
            },
            "reference_sha256": sha(output),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
