"""Compare the frozen v4 kernel with current physical bureau/root accounting.

Known charts and generated civil inputs are exposed engineering regression.
Neither unchanged labels nor numeric shifts certify complete classical strength.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from audit_bazi_root_qualification import V4_ARCHIVE, V4_SHA256, _load_archive

from fatebridge.core import strength
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.elements import ElementAnalysis

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "tests/fixtures/bazi_complete_bureau_v1"
ORDER = ("year", "month", "day", "hour")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict[str, Any]:
    for name in (
        "core.strength",
        "core.elements",
        "core.storage_movement",
        "core.classical_roots",
        "utils.data",
    ):
        loaded = getattr(sys.modules["fatebridge." + name], "__file__", None)
        expected = ROOT / "src/fatebridge" / (name.replace(".", "/") + ".py")
        if loaded is None or Path(loaded).resolve() != expected.resolve():
            raise RuntimeError(f"Numerical module is not from this source tree: {name}")
    reference = FOLDER / "reference.json"
    if sha(reference) != reference.with_suffix(".sha256").read_text().strip():
        raise ValueError("Source annotation changed after freeze")
    source = json.loads(reference.read_text())
    if sha(FOLDER / "source-pages.pdf") != source["source"]["retained_pages_sha256"]:
        raise ValueError("Retained source pages changed")
    baseline = _load_archive(V4_ARCHIVE, V4_SHA256, "v4")
    chart = dict(
        zip(ORDER, [(p[0], p[1]) for p in source["case"]["pillars"]], strict=True)
    )
    probes = [(source["case"]["id"], chart)]
    for year in range(2000, 2010):
        for month in range(1, 13):
            for hour in (0, 6, 12, 18):
                instant = datetime(
                    year, month, 15, hour, tzinfo=ZoneInfo("Asia/Shanghai")
                )
                probes.append(
                    (
                        instant.isoformat(),
                        BaZiCalendar.get_four_pillars(
                            instant,
                            timezone_name="Asia/Shanghai",
                            civil_datetime=instant,
                        ),
                    )
                )
    fingerprints = {
        p: sha(ROOT / p)
        for p in [
            "src/fatebridge/core/strength.py",
            "src/fatebridge/core/complete_bureaus.py",
            "src/fatebridge/core/storage_movement.py",
            "src/fatebridge/core/classical_roots.py",
            "src/fatebridge/core/elements.py",
            "src/fatebridge/utils/data.py",
            "uv.lock",
        ]
    }
    numeric_changes, root_receipt_changes, conservation_failures = [], [], []
    source_observation = None
    for index, (label, chart) in enumerate(probes):
        phases = ElementAnalysis.seasonal_phases(chart["month"][1])
        before = baseline._evaluate(chart, phases, baseline.DEFAULT_POLICY)
        after = strength._evaluate(chart, phases, strength.DEFAULT_POLICY)
        row = {
            "case_id": label,
            "pillars": ["".join(chart[p]) for p in ORDER],
            "before_strength": before["strength_level"],
            "after_strength": after["strength_level"],
            "before_support_share": before["support_share"],
            "after_support_share": after["support_share"],
        }
        changed = [
            f
            for f in [
                "support_strength",
                "weaken_strength",
                "support_share",
                "effective_elements",
                "strength_level",
            ]
            if before[f] != after[f]
        ]
        if changed:
            numeric_changes.append({**row, "changed_fields": changed})
        if [r["root_mass"] for r in before["revealed_stems"]] != [
            r["root_mass"] for r in after["revealed_stems"]
        ]:
            root_receipt_changes.append(label)
        for p, budget in after["branch_budgets"].items():
            real = sum(
                r["remaining_mass"]
                for r in after["hidden_stem_ledger"]
                if r["pillar"] == p
            )
            synthetic = sum(
                r["mass"]
                for r in after["combination_contributions"]
                if r["pillar"] == p
            )
            if (
                abs(real + synthetic - budget["remaining"]) > 1e-12
                or budget["remaining"] > budget["initial"] + 1e-12
            ):
                conservation_failures.append({"case_id": label, "position": p})
        if index == 0:
            source_observation = {
                **row,
                "before_relations": before["relations"],
                "after_relations": after["relations"],
                "after_hidden_stem_ledger": after["hidden_stem_ledger"],
            }
    small = dict(
        zip(ORDER, [(p[0], p[1]) for p in "甲寅 丙午 丙辰 丁酉".split()], strict=True)
    )
    phases = ElementAnalysis.seasonal_phases(small["month"][1])
    before = baseline._evaluate(
        small, phases, replace(baseline.DEFAULT_POLICY, branch_budget=0.5)
    )
    after = strength._evaluate(
        small, phases, replace(strength.DEFAULT_POLICY, branch_budget=0.5)
    )
    old_fire = next(r for r in before["revealed_stems"] if r["pillar"] == "month")
    new_fire = next(r for r in after["revealed_stems"] if r["pillar"] == "month")
    if any(sha(ROOT / p) != h for p, h in fingerprints.items()):
        raise ValueError("Numerical dependency drift during comparison")
    assert source_observation is not None
    events = [r for r in source_observation["after_relations"] if r["kind"] == "三合"]
    source_predicate = (
        len(events) == 1
        and events[0]["target"] == "金"
        and len(events[0]["positions"]) == 4
        and events[0]["status"] in {"binding", "conditioned_transformation"}
    )
    return {
        "report_id": "complete_bureau_and_physical_roots_v1",
        "baseline_kernel_sha256": V4_SHA256,
        "current_method_id": strength.STRENGTH_METHOD_ID,
        "baseline_scope": "Exact archived v4 kernel with explicitly fingerprinted current shared dependencies; not a fully archived historical environment.",
        "source": source,
        "reference_sha256": sha(reference),
        "dependencies": fingerprints,
        "source_predicate_matches": source_predicate,
        "source_observation": source_observation,
        "probe_count": len(probes),
        "civil_input_probes": len(probes) - 1,
        "numeric_change_count": len(numeric_changes),
        "numeric_changes": numeric_changes,
        "strength_label_changes": [
            r for r in numeric_changes if r["before_strength"] != r["after_strength"]
        ],
        "root_mass_receipt_change_count": len(root_receipt_changes),
        "root_mass_receipt_changed_cases": root_receipt_changes,
        "budget_conservation_failures": conservation_failures,
        "physical_root_ablation": {
            "classification": "controlled engineering fixture, not an original source example",
            "branch_budget": 0.5,
            "before": old_fire,
            "after": new_fire,
            "manual_root_mass": "17/21 from 寅中丙 and 午中丁 only",
            "manual_stem_energy": "12/7 using unchanged activation and seasonal factors",
        },
        "numeric_parameters_changed": False,
        "classification": "Source-collated local relation repair plus exposed engineering regression; not a blind accuracy trial or complete classical force model.",
        "classical_acceptance_passed": False,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Audit outputs are immutable; choose a new path")
    result = audit()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "probe_count",
                    "numeric_change_count",
                    "root_mass_receipt_change_count",
                    "source_predicate_matches",
                    "classical_acceptance_passed",
                ]
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if result["source_predicate_matches"]
        and not result["budget_conservation_failures"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
