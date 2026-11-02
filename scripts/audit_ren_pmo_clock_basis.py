"""Replay a post-hoc UT1 hypothesis without changing the PMO minute gate.

Inputs are the same 113 frozen JPL anchors and five saved production reports.
No production calculation, new event or standards certification is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_calendar_standard_v1"
PIN = "3f39e6854075f034c3396bf41b33f392720eb821a60a241258eba86369e35890"
INERTIAL_PIN = "44cca16b007961b000e81bc949a2690560922ee7571aebeae90205ad02df4856"
READER_PIN = "81d18e268688a7a78b502f9bc8b4955e9b4a236b9b0b062bbbfbe588f14c8125"
REPORT = ROOT / "docs/validation/ren-horizons-tt-audit-2026-10-26.json"
REPORT_PIN = "fa5c5c0499eed48decfbd38a524bfda0887749cbd7328354517310f82057c31e"
PROFILES = ["native_swiss", "native_moshier", "analytic", "de440", "spk"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_reading(folder: Path = CORPUS) -> dict[str, Any]:
    if sha(folder / "freeze.json") != PIN:
        raise ValueError("Official reading identity changed")
    files = json.loads((folder / "freeze.json").read_text())["files"]
    if {p.name for p in folder.iterdir()} != set(files) | {"freeze.json"}:
        raise ValueError("Official reading inventory changed")
    if any(sha(folder / n) != h for n, h in files.items()):
        raise ValueError("Official reading content changed")
    reading: dict[str, Any] = json.loads((folder / "reading.json").read_text())
    return reading


def saved_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    if sha(REPORT) != REPORT_PIN:
        raise ValueError("Original five-profile report identity changed")
    if (
        sha(ROOT / "tests/fixtures/ren_horizons_inertial_v1/freeze.json")
        != INERTIAL_PIN
    ):
        raise ValueError("Original JPL anchor identity changed")
    reader = ROOT / "scripts/audit_ren_horizons_inertial.py"
    if sha(reader) != READER_PIN:
        raise ValueError("Original raw response reader identity changed")
    # This rebuilds quantity49 from the frozen requests and raw responses.
    spec = importlib.util.spec_from_file_location("frozen_inertial_reader", reader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reference(), json.loads(REPORT.read_text())


def seconds(value: Any) -> Decimal:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("A finite numeric offset is required")
    return Decimal(str(value))


def diagnose(reference: dict[str, Any], reports: dict[str, Any]) -> dict[str, Any]:
    cases = reference["protocol"]["cohort"]
    anchors = reference["rows"]
    profiles = reports["profiles"]
    if (
        len(cases) != 113
        or len(anchors) != 113
        or len({(c["year"], c["term"]) for c in cases}) != 113
        or [p["profile"] for p in profiles] != PROFILES
    ):
        raise ValueError("All original 113 anchors and five profiles are required")
    results = []
    for profile in profiles:
        rows = profile["comparisons"]
        if len(rows) != 113 or profile["expected_count"] != 113:
            raise ValueError("The complete saved event denominator is required")
        output = []
        for case, anchor, row in zip(cases, anchors, rows, strict=True):
            if (
                (row["year"], row["term"]) != (case["year"], case["term"])
                or anchor["timestamp_label"] != case["query_label"]
                or row["error"] is not None
                or row["source_identity_matches"] is not True
            ):
                raise ValueError(
                    "Saved event, anchor or actual source identity differs"
                )
            actual = datetime.fromisoformat(row["actual"]["civil_datetime"])
            printed = datetime.fromisoformat(case["published_moment"])
            if actual.utcoffset() is None or printed.utcoffset() is None:
                raise ValueError("Civil labels must retain their offsets")
            delta = actual - printed
            utc = Decimal(
                (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
            ) / Decimal(1000000)
            if utc != seconds(row["actual_minus_printed_civil_seconds"]) or row[
                "within_original_pmo_numeric_criterion"
            ] is not (abs(utc) <= 30):
                raise ValueError(
                    "Saved civil calculation or original 30s grade differs"
                )
            dut1 = anchor["UT1-UTC"]
            hypothetical = None if dut1 is None else utc + seconds(dut1)
            output.append(
                {
                    "year": case["year"],
                    "term": case["term"],
                    "published_moment": case["published_moment"],
                    "dut1_evaluation_label": anchor["timestamp_label"],
                    "dut1_evaluation_time_scale": case["label_time_scale"],
                    "original_civil_label_delta_seconds": float(utc),
                    "dut1_seconds": dut1,
                    "hypothetical_ut1_delta_seconds": (
                        None if hypothetical is None else float(hypothetical)
                    ),
                    "original_civil_numeric_pass": abs(utc) <= 30,
                    "hypothetical_ut1_pass": (
                        None if hypothetical is None else abs(hypothetical) <= 30
                    ),
                }
            )
        known = [r for r in output if r["dut1_seconds"] is not None]
        results.append(
            {
                "profile": profile["profile"],
                "expected_events": 113,
                "retained_events": len(output),
                "dut1_unknown_count": len(output) - len(known),
                "all_original_civil_numeric_failures": sum(
                    not r["original_civil_numeric_pass"] for r in output
                ),
                "known_dut1_utc_failures": sum(
                    not r["original_civil_numeric_pass"] for r in known
                ),
                "known_dut1_hypothetical_ut1_failures": sum(
                    r["hypothetical_ut1_pass"] is False for r in known
                ),
                "rows": output,
            }
        )
    return {
        "kind": "posthoc_saved_report_diagnosis",
        "source_reading_pin": PIN,
        "original_report_pin": REPORT_PIN,
        "jpl_anchor_pin": INERTIAL_PIN,
        "raw_reader_pin": READER_PIN,
        "profiles": results,
        "unique_events": 113,
        "new_unique_events": 0,
        "production_calculations_performed": False,
        "dut1_evaluated_at_printed_anchor_not_actual_root": True,
        "civil_delta_scope": "Saved software civil labels; historical UTC-like labels are not independently certified physical UTC. Hypothetical UT1 is computed only where original JPL DUT1 is available.",
        "original_criterion_seconds": 30,
        "original_minute_gate_reclassified": False,
        "ut1_adopted_as_beijing_time": False,
        "printed_minute_rounding_established": False,
        "full_standard_conformance_established": False,
        "goal_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_reading()
    result = diagnose(*saved_inputs())
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "replay_completed": True,
                "production_calculations_performed": False,
                "profiles": [
                    {k: v for k, v in p.items() if k != "rows"}
                    for p in result["profiles"]
                ],
                "original_minute_gate_reclassified": False,
                "goal_complete": False,
            },
            ensure_ascii=False,
        )
    )
    return 0  # Complete replay only; never a calendar-acceptance exit status.


if __name__ == "__main__":
    raise SystemExit(main())
