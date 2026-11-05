"""Compare complete natal output with frozen software charts, offline.

This is software compatibility evidence. It does not establish the correctness
of iztro, classical textual adjudication, or predictive efficacy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.services.metaphysics import _build_analysis_seed

FIXTURES = Path(__file__).resolve().parents[1] / "tests/data/ziwei_independent"


def audit_natal(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "natal_manifest.json").read_text(encoding="utf-8")
    )
    source = manifest["files"][0]
    data = (fixtures / source["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError("Natal reference checksum mismatch")
    records = json.loads(data)
    if len(records) != manifest["case_count"]:
        raise ValueError("Natal reference case count mismatch")
    differences, stars_checked, cycle_cells = [], 0, 0
    stem_set, year_branch_set, hour_set = set(), set(), set()
    for case in records:
        year, month, day = (int(x) for x in case["solar"].split("-"))
        time_index = case["input"]["hour"]
        seed = _build_analysis_seed(
            analysis_year=year,
            analysis_month=month,
            analysis_day=day,
            analysis_hour=23 if time_index == 12 else time_index * 2,
        )
        chart = build_ziwei_chart(seed, case["input"]["gender"])
        label = case["input"]["id"]

        def compare(field: str, actual: Any, expected: Any) -> None:
            if actual != expected:
                differences.append(
                    {
                        "case": label,
                        "field": field,
                        "expected": expected,
                        "actual": actual,
                    }
                )

        actual_stars = {
            s["name"]: [p["ganzhi"][1], s["brightness"], s["mutagen"]]
            for p in chart["palaces"]
            for s in p["stars_detail"]
        }
        compare("stars", actual_stars, case["stars"])
        reading_stars = {
            s["name"]: [p["ganzhi"][1], s.get("brightness"), s.get("mutagen")]
            for p in chart["reading_view"]["palaces"]
            for s in p["stars"]
        }
        compare("reading_view.stars", reading_stars, case["stars"])
        stars_checked += len(case["stars"])
        compare("ming", chart["ming_gong"]["branch"], case["ming"])
        compare("shen", chart["shen_gong"]["branch"], case["shen"])
        compare("ju", chart["wuxing_ju"]["label"], case["ju"])
        compare(
            "lunar",
            chart["lunar_date"],
            {
                "year": case["lunar"]["lunarYear"],
                "month": case["lunar"]["lunarMonth"],
                "day": case["lunar"]["lunarDay"],
                "is_leap_month": case["lunar"]["isLeap"],
            },
        )
        compare(
            "masters",
            [
                chart["chart_masters"]["life"]["star"],
                chart["chart_masters"]["body"]["star"],
            ],
            [case["soul"], case["body"]],
        )
        for palace in case["palaces"]:
            natal = next(p for p in chart["palaces"] if p["ganzhi"] == palace["ganzhi"])
            expected_name = (
                palace["name"] if palace["name"] == "命宫" else palace["name"] + "宫"
            )
            compare(f"{palace['ganzhi']}/name", natal["name"], expected_name)
            compare(
                f"{palace['ganzhi']}/cycles",
                [natal["changsheng12"], natal["boshi12"]],
                [palace["changsheng"], palace["boshi"]],
            )
            compare(
                f"{palace['ganzhi']}/daxian",
                natal["daxian"],
                "~".join(str(age) for age in palace["daxian"]),
            )
            cycle_cells += 2
        stem_set.add(chart["year_stem"])
        year_branch_set.add((int(case["lunar"]["lunarYear"]) - 4) % 12)
        hour_set.add(chart["hour_branch"])
    return {
        "status": "pass_in_frozen_corpus" if not differences else "failed",
        "oracle": manifest["oracle"],
        "oracle_version": manifest["oracle_version"],
        "source": manifest["source"],
        "config": manifest["config"],
        "case_count": len(records),
        "star_records_checked": stars_checked,
        "cycle_cells_checked": cycle_cells,
        "year_stem_coverage": len(stem_set),
        "year_branch_coverage": len(year_branch_set),
        "hour_branch_coverage": len(hour_set),
        "differences": differences,
        "limits": manifest["limits"],
        "whole_input_space_certified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_natal()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    raise SystemExit(0 if not result["differences"] else 1)


if __name__ == "__main__":
    main()
