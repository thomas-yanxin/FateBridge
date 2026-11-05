"""Replay two frozen Key examples through explicit historical-date adapters.

Calendar observations and full classical observations have separate counts.
The latter keep every V6/V7 disagreement and unknown; they still fail acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fatebridge.core.almanac import get_day_ganzhi
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.core.metaphysics.taiyi_historical import julian_to_proleptic_gregorian
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_day import audit as day_audit
from scripts.taiyi.audit_taiyi_hour import audit as hour_audit

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v8"
SOURCE_IDS = {
    "ming-1561-month11-start",
    "key-1561-dingwei-day",
    "ming-1561-month12-start",
    "key-1561-dingchou-xu-hour",
}


def public_case(
    row: dict[str, Any], *, selected_date: str | None = None
) -> dict[str, Any]:
    d = date.fromisoformat(selected_date or row["gregorian_date"])
    return calculate_taiyi_analysis(
        analysis_year=d.year,
        analysis_month=d.month,
        analysis_day=d.day,
        analysis_hour=int(row["representative_clock"][:2]),
        analysis_timezone="+08:00",
        calculation_mode=row["mode"],
        hour_profile="key_hour_winter_jiazi_v1" if row["mode"] == "hour" else None,
        use_true_solar_time=False,
    )


def _compare(rows: list[dict[str, Any]]) -> dict[str, Any]:
    differences = [
        r for r in rows if r["actual"] is not None and r["actual"] != r["expected"]
    ]
    unknown = [r for r in rows if r["actual"] is None]
    return {
        "required_observations": len(rows),
        "evaluated_observations": len(rows) - len(unknown),
        "matching_observations": len(rows) - len(differences) - len(unknown),
        "disagreements": differences,
        "unadjudicated": unknown,
        "source_example_acceptance_passed": not differences and not unknown,
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    if {r["file"] for r in manifest["source_files"]} != {"sino-western-printed313.jpg"}:
        raise ValueError("独立历表图像不得删除")
    if {r["file"] for r in manifest["prior_source_references"]} != {
        "../taiyi_jinjing_v6/hour-worked.json",
        "../taiyi_jinjing_v7/day-worked.json",
    }:
        raise ValueError("既有完整日时课例不能替换为匹配子集")
    for item in (
        manifest["source_files"]
        + manifest["prior_source_references"]
        + [manifest["source_reference"]]
    ):
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("历史日期冻结来源指纹不符：" + item["file"])
    # Preserve the original audit's whole-source and denominator guards.
    day_audit(corpus.parent / "taiyi_jinjing_v7")
    hour_audit(corpus.parent / "taiyi_jinjing_v6")
    source = json.loads((corpus / manifest["source_reference"]["file"]).read_text())
    if (
        len(source["records"]) != 4
        or {r["id"] for r in source["records"]} != SOURCE_IDS
    ):
        raise ValueError("两个月首与两条课例日期四观察不得删减")
    calendar, replays = [], {}
    for row in source["records"]:
        julian = date.fromisoformat(row["julian_date"])
        actual = julian_to_proleptic_gregorian(julian.year, julian.month, julian.day)
        gz = get_day_ganzhi(actual.year, actual.month, actual.day)
        match = actual.isoformat() == row["gregorian_date"] and gz == row["day_ganzhi"]
        if "printed_cycle_index" in row:
            match &= SEXAGENARY_INDEX[gz] == row["printed_cycle_index"]
            match &= actual.weekday() == row["printed_weekday_monday_zero"]
        calendar.append(
            {
                **row,
                "converted_date": actual.isoformat(),
                "computed_day_ganzhi": gz,
                "matches": match,
            }
        )
        if "mode" not in row:
            continue
        result = public_case(row)
        if "error" in result:
            raise ValueError(result["error"])
        board = result["taiyi"]
        reference = board["calendar_rules"]["historical_date_reference"]
        if (
            not reference["counter_matches"]
            or not reference["day_ganzhi_matches"]
            or reference["hour_branch_matches"] is False
        ):
            raise ValueError("日期对照不等于实际公开计数通过")
        if row["mode"] == "day":
            frozen = json.loads(
                (corpus.parent / "taiyi_jinjing_v7/day-worked.json").read_text()
            )
            observed = []
            for observation in frozen["observations"]:
                value: Any = board
                for key in observation["result_path"].split("."):
                    value = value[key]
                observed.append({**observation, "actual": value})
        else:
            frozen = json.loads(
                (corpus.parent / "taiyi_jinjing_v6/hour-worked.json").read_text()
            )
            actuals = {
                **board["core_board"],
                "wenchang_palace": board["wenchang_palace"],
                **{
                    k: board["gates"]["counter"][k]
                    for k in ("duty_gate", "unit_in_gate")
                },
                "menju_jiangfa": board["condition_assessment"]["menju_jiangfa"],
            }
            observed = [
                {"id": k, "expected": v, "actual": actuals[k]}
                for k, v in frozen["expected"].items()
            ]
        replays[row["mode"]] = {
            "case_id": row["id"],
            "historical_date_reference": reference,
            **_compare(observed),
        }
    return {
        "completion_claim": False,
        "calendar_observations": calendar,
        "selected_calendar_observations_passed": all(r["matches"] for r in calendar),
        "public_historical_replays": replays,
        "full_classical_acceptance_passed": all(
            r["source_example_acceptance_passed"] for r in replays.values()
        ),
        "scope": "两个月首日期、两条课例日期与固定+08:00现代适配；原时地未复原，代表钟面不是古例分秒。日34项与时20项独立计数，不能混入4日期来抬高原典匹配率。",
        "full_ancient_calendar_reconstructed": False,
        "whole_book_conformance": "not_established",
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return (
        0
        if report["selected_calendar_observations_passed"]
        and report["full_classical_acceptance_passed"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
