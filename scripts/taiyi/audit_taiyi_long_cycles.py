"""Audit all volume-five raw cells; fail while any textual disagreement remains."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_long_cycles import (
    annual_long_cycles,
    four_spirit_records,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v3"
STARS = ("sishen", "tianyi", "diyi", "zhifu")
YUANS = ("upper", "middle", "lower")
COLUMNS = {s + "." + y for s in STARS for y in YUANS}


def walk_spirits(year_count: int) -> list[dict[str, tuple[str, int]]]:
    """Step one year at a time from the printed origins, without modular arithmetic."""
    palace_order = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "绛", "明", "玉"]
    palace_indices = {"sishen": 0, "tianyi": 5, "diyi": 8, "zhifu": 4}
    dwell_year = 1
    years = []
    for _ in range(year_count):
        years.append(
            {
                star: (palace_order[index], dwell_year)
                for star, index in palace_indices.items()
            }
        )
        if dwell_year == 3:
            dwell_year = 1
            palace_indices = {
                star: 0 if index == 11 else index + 1
                for star, index in palace_indices.items()
            }
        else:
            dwell_year += 1
    return years


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    required = {
        "vol05.html",
        "vol05.txt",
        "four-spirit-cases.json",
        "worked-cases.json",
        "collation.json",
        "page-locations.json",
        *{
            f"cadal06056495-page{page}.jpg"
            for page in (4, 5, 7, 8, 12, 13, 15, 16, *range(23, 32))
        },
        *{f"ncl06604-page{page}.jpg" for page in range(71, 75)},
    }
    if not required <= {item["file"] for item in manifest["source_files"]}:
        raise ValueError("不得删除原典或完整验收集的来源记录")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("冻结来源指纹不符：" + item["file"])
    table = json.loads((corpus / "four-spirit-cases.json").read_text(encoding="utf-8"))
    if (
        sorted(r["year_index"] for r in table["rows"]) != list(range(1, 61))
        or set(table["columns"]) != COLUMNS
    ):
        raise ValueError("卷五原表必须包含全部60行及12列，不得删除失败项")
    locations = json.loads((corpus / "page-locations.json").read_text(encoding="utf-8"))
    disputed_cell_pages = {
        row_index: (
            span["last_row_cell_page"]
            if row_index == span["last_year_index"]
            else span["row_start_page"]
        )
        for span in locations["disputed_row_spans"]
        for row_index in range(span["first_year_index"], span["last_year_index"] + 1)
    }
    collation = json.loads((corpus / "collation.json").read_text(encoding="utf-8"))
    confirmed_readings = {
        (cell["year_index"], cell["field"], cell["reading"])
        for cell in collation["disputed_cells"]
    }
    differences = []
    passed = 0
    by_star = {s: {"checked": 0, "matching": 0} for s in STARS}
    for row in table["rows"]:
        if set(row["expected"]) != COLUMNS:
            raise ValueError("每行必须核对全部12个原表宫位")
        for field, expected in row["expected"].items():
            star, yuan = field.split(".")
            acc = row["year_index"] + 60 * YUANS.index(yuan)
            result = four_spirit_records(acc)[star]["position"]
            by_star[star]["checked"] += 1
            if result == expected:
                passed += 1
                by_star[star]["matching"] += 1
            else:
                differences.append(
                    {
                        "row_id": row["id"],
                        "ganzhi": row["ganzhi"],
                        "year_index": row["year_index"],
                        "field": field,
                        "source_value": expected,
                        "source_cell_page": (
                            disputed_cell_pages.get(row["year_index"])
                            if field == "zhifu.middle"
                            else None
                        ),
                        "rule_derived_value": result,
                        "status": (
                            "facsimile_confirms_raw_reading_rule_table_disagreement_unresolved"
                            if (row["year_index"], field, expected)
                            in confirmed_readings
                            else "uncollected_table_reading_not_facsimile_confirmed"
                        ),
                    }
                )
    walking_matches = 0
    repeated_table_matches = 0
    for accumulation, reference in enumerate(walk_spirits(540), start=1):
        for star, (position, dwell_year) in reference.items():
            actual = four_spirit_records(accumulation)[star]
            walking_matches += (actual["position"], actual["year_in_palace"]) == (
                position,
                dwell_year,
            )
            phase = (accumulation - 1) % 180
            source_row = next(
                row for row in table["rows"] if row["year_index"] == phase % 60 + 1
            )
            repeated_table_matches += (
                source_row["expected"][star + "." + YUANS[phase // 60]] == position
            )
    expected_worked_fields = {
        "five-fu-724": {"wufu.palace", "wufu.year_in_palace", "wufu.accumulation"},
        "junji-915-miao-2019": {
            "junji.palace",
            "junji.year_in_palace",
            "junji.accumulation",
            "junji.cycle_year",
        },
        "epochs-724": {
            name + ".accumulation"
            for name in (
                "junji",
                "chenji",
                "minji",
                "wufu",
                "dayou",
                "dayou_tianmu",
                "xiaoyou",
                *STARS,
            )
        },
        "ncl-xiaoyou-904": {"xiaoyou.palace_number"},
        "ncl-sishen-907": {"sishen.palace_number"},
        "ncl-tianyi-622": {"tianyi.palace"},
        "ncl-dayou-930": {"dayou.palace_number"},
        "ncl-diyi-934": {"diyi.palace"},
        "ncl-zhifu-976": {"zhifu.palace_number"},
    }
    worked_cases = json.loads(
        (corpus / "worked-cases.json").read_text(encoding="utf-8")
    )
    if sorted(case["id"] for case in worked_cases) != sorted(expected_worked_fields):
        raise ValueError("必须保留全部9个具名算例")
    worked = []
    for case in worked_cases:
        observed_fields = {
            name + "." + field
            for name, fields in case.get("expected", {}).items()
            for field in fields
        } | {name + ".accumulation" for name in case.get("expected_accumulations", {})}
        if observed_fields != expected_worked_fields[case["id"]]:
            raise ValueError("必须保留算例全部24个具名字段")
        records = annual_long_cycles(case["year"])["records"]
        expected = case.get("expected", {})
        checks = [
            records[k][f] == v
            for k, fields in expected.items()
            for f, v in fields.items()
        ]
        checks += [
            records[k]["accumulation"] == v
            for k, v in case.get("expected_accumulations", {}).items()
        ]
        worked.append(
            {
                "id": case["id"],
                "checked_fields": len(checks),
                "matching_fields": sum(checks),
                "passed": all(checks),
                "oracle_kind": case["oracle_kind"],
                "source": case["source"],
            }
        )
    return {
        "ruleset": "jinjing_annual_ten_markers_v1",
        "oracle_kind": "independent_manual_source_table_not_production_output",
        "source_rows": 60,
        "source_columns": 12,
        "checked_fields": 720,
        "matching_fields": passed,
        "by_star": by_star,
        "disagreements": differences,
        "worked_examples": worked,
        "integer_walker": {
            "oracle_kind": "independent_implementation_of_same_prose_rule_not_independent_book_witness",
            "accumulation_range": [1, 540],
            "checked_marker_pairs": 2160,
            "matching_marker_pairs": walking_matches,
            "fields_per_pair": ["position", "year_in_palace"],
            "repeated_table_checked_fields": 2160,
            "repeated_table_matching_fields": repeated_table_matches,
        },
        "classical_acceptance_passed": not differences
        and walking_matches == 2160
        and all(c["passed"] for c in worked),
        "whole_book_conformance": "not_established",
        "scope_limit": "宫位和年序的有限来源核验，不认证全书、分野断法或现实预测。",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "src/fatebridge/core/metaphysics/taiyi_long_cycles.py").read_bytes()
        ).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = audit(arguments.corpus)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        print(serialized, end="")
    else:
        arguments.output.write_text(serialized, encoding="utf-8")
    raise SystemExit(0 if report["classical_acceptance_passed"] else 1)
