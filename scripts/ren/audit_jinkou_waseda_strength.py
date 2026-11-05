"""Compare the full twelve-row manuscript witness, retaining the CNTS failure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_waseda_strength_v1"
PIN = "17bade2ba4ee89f20cf1b3b8d71de75a6351275b595e7d438bd8a268c98e6628"
WATCH = (
    "src/fatebridge/core/metaphysics/jinkou_sources.py",
    "src/fatebridge/core/metaphysics/jinkou_strength.py",
    "src/fatebridge/core/output_jinkou_sources.py",
    "src/fatebridge/core/output_jinkou_strength.py",
    "src/fatebridge/data/jinkou_waseda_strength.json",
    "scripts/ren/audit_jinkou_waseda_strength.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference() -> dict[str, Any]:
    if sha(CORPUS / "freeze.json") != PIN:
        raise ValueError("Frozen primary strength protocol changed")
    files = json.loads((CORPUS / "freeze.json").read_text())["files"]
    if {p.name for p in CORPUS.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Frozen primary strength inventory changed")
    if any(sha(CORPUS / n) != d for n, d in files.items()):
        raise ValueError("Frozen primary strength source changed")
    data: dict[str, Any] = json.loads((CORPUS / "readings.json").read_text())
    if len(data["cases"]) != 12 or len({c["id"] for c in data["cases"]}) != 12:
        raise ValueError("All twelve original examples are required")
    return data


def audit() -> dict[str, Any]:
    ref = reference()
    protocol = json.loads((CORPUS / "protocol.json").read_text())
    before = {n: sha(ROOT / n) for n in WATCH}
    from fatebridge.core.metaphysics.jinkou_sources import strength_sources
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength
    from scripts.ren.audit_jinkou_strength import audit as original_audit

    if (
        sha(ROOT / "tests/fixtures/jinkou_strength_scan_v1/freeze.json")
        != protocol["original_source_freeze_sha256"]
    ):
        raise ValueError("Original CNTS witness changed")
    asset = strength_sources()
    assert asset["primary_witness"] == ref["witness"]
    rows = []
    for case in ref["cases"]:
        value = internal_strength(
            [
                dict(label=p, element=e)
                for p, e in zip(ref["positions"], case["elements"], strict=True)
            ]
        )
        rows.append(
            dict(
                id=case["id"],
                raw_god=case["raw_god"],
                raw_four_tokens=case["raw_four_tokens"],
                elements=case["elements"],
                original_pdf_pages=case["original_pdf_pages"],
                expected_anchor=case["stated_anchor"],
                actual_anchor=value["anchor_element"],
                expected_power=case["stated_god_power"],
                actual_power=value["powers"]["贵神"],
                matched=case["stated_anchor"] == value["anchor_element"]
                and case["stated_god_power"] == value["powers"]["贵神"],
            )
        )
    old = original_audit()
    unchanged = before == {n: sha(ROOT / n) for n in WATCH}
    return dict(
        audit_id="jinkou_waseda_strength_v1",
        reference_sha256=PIN,
        implementation_sha256=before,
        implementation_unchanged=unchanged,
        waseda_rows=rows,
        waseda_matched=sum(r["matched"] for r in rows),
        waseda_total=len(rows),
        primary_metadata_matches_source=True,
        original_cnts_matched=old["scan_matched_count"],
        original_cnts_total=old["scan_case_count"],
        original_cnts_failures=old["scan_failures"],
        original_cnts_classical_gate=old["classical_acceptance_passed"],
        older_online_matched=old["older_online_matched_count"],
        same_symbolic_family_not_24_independent_events=True,
        new_independent_historical_events=0,
        independent_textual_transmission_adjudicated=False,
        full_volume_collation=False,
        full_daily_five_states_adjudicated=False,
        full_comprehensive_use_adjudicated=False,
        engineering_checks_passed=unchanged
        and all(r["matched"] for r in rows)
        and old["scan_matched_count"] == 11
        and old["scan_case_count"] == 12
        and not old["classical_acceptance_passed"],
        full_calendar_acceptance=False,
        full_classical_acceptance=False,
        free_model_interpretation_revalidated=False,
        new_model_processes=0,
        real_world_validation="deferred_by_user",
        goal_complete=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "waseda_matched",
                    "waseda_total",
                    "original_cnts_matched",
                    "original_cnts_total",
                    "engineering_checks_passed",
                    "goal_complete",
                ]
            }
        )
    )
    return 0 if report["engineering_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
