"""Audit frozen civil-date evidence and text fidelity; full calendar remains open."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.services.metaphysics import calculate_taiyi_analysis

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/taiyi_jinjing_v27"
FREEZE_SHA256 = "d8747b682c192375670f1f8db1d5eed1e900f7417e0000c2d9e185454a740871"


def verify_sources(corpus: Path = CORPUS) -> dict[str, Any]:
    raw = (corpus / "freeze.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != FREEZE_SHA256:
        raise ValueError("V27 original source freeze changed")
    freeze = json.loads(raw)
    if not isinstance(freeze, dict):
        raise ValueError("V27 source freeze must be an object")
    for name, digest in freeze["files"].items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"V27 frozen file changed: {name}")
    return freeze


def public_input(case: dict[str, Any], *, solar: bool = True) -> dict[str, Any]:
    return {
        **{
            f"analysis_{k}": case[k] for k in ("year", "month", "day", "hour", "minute")
        },
        "analysis_timezone": "+08:00",
        "analysis_longitude": 0.0,
        "use_true_solar_time": solar,
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = verify_sources(corpus)
    cases = json.loads((corpus / "cases.json").read_text())["cases"]
    rows = []
    for case in cases:
        result = calculate_taiyi_analysis(**public_input(case))
        if "taiyi" not in result:
            raise ValueError(f"V27 public calculation failed: {case['id']}: {result}")
        board = result["taiyi"]
        evidence = board["calendar_rules"]["civil_lunar_calendar"]
        actual = [evidence[k] for k in ("year", "month", "day", "is_leap_month")]
        source = evidence["conversion_source"]
        source_id = source.get("method_id") if source else None
        context = result["analysis_context"]
        rows.append(
            {
                "id": case["id"],
                "source_file": case["source"],
                "expected_lunar": case["expected_lunar"],
                "actual_lunar": actual,
                "date_matches": actual == case["expected_lunar"],
                "source_matches": source_id == case["expected_source"],
                "conversion_source": source,
                "actual_year_matches_used_lunar": board["calendar_rules"]["year"]
                == evidence["year"],
                "input_datetime": context["input_datetime"],
                "corrected_datetime": context["corrected_datetime"],
                "time_context_lunar_display": context["lunar_display"],
                "used_lunar_date": evidence["display"],
                "snapshot_uses_actual_lunar_date": (
                    f"年计所用农历：{evidence['display']}" in result["snapshot_text"]
                ),
                "snapshot_retains_both_clocks": all(
                    text in result["snapshot_text"]
                    for text in (
                        f"输入钟时：{context['input_datetime'].replace(' ', 'T')}",
                        f"计算钟面：{context['corrected_datetime']}",
                    )
                ),
                "classical_acceptance_passed": board["ruleset"][
                    "classical_acceptance_passed"
                ],
            }
        )
    flags = (
        "date_matches",
        "source_matches",
        "actual_year_matches_used_lunar",
        "snapshot_uses_actual_lunar_date",
        "snapshot_retains_both_clocks",
    )
    return {
        "freeze_sha256": FREEZE_SHA256,
        "source_files": freeze["files"],
        "fictional_boundary_cases": len(cases),
        "matching_calendar_dates": sum(row["date_matches"] for row in rows),
        "civil_date_evidence_and_text_checks_passed": all(
            row[flag] for row in rows for flag in flags
        ),
        "cases": rows,
        "independent_solar_time_validation": False,
        "new_dated_classical_cases": 0,
        "full_ancient_calendar_reconstructed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": (
            "Three fictional +08:00 civil-date boundary cases at longitude0; "
            "institutional lunar labels test the annual adapter and text. "
            "They do not validate solar correction, every timezone, ancient "
            "calendar reconstruction, full classical rules or model behavior."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw)
    raise SystemExit(1)  # A bounded repair cannot close the full calendar goal.


if __name__ == "__main__":
    main()
