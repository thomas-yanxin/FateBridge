"""Audit all volume-five raw cells; fail while any textual disagreement remains."""

from __future__ import annotations

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


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    required = {
        "vol05.html",
        "vol05.txt",
        "four-spirit-cases.json",
        "worked-cases.json",
        "collation.json",
    }
    if not required <= {item["file"] for item in manifest["source_files"]}:
        raise ValueError("不得删除原典或完整验收集的来源记录")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("冻结来源指纹不符：" + item["file"])
    table = json.loads((corpus / "four-spirit-cases.json").read_text())
    if (
        sorted(r["year_index"] for r in table["rows"]) != list(range(1, 61))
        or set(table["columns"]) != COLUMNS
    ):
        raise ValueError("卷五原表必须包含全部60行及12列，不得删除失败项")
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
                        "rule_derived_value": result,
                        "status": "facsimile_confirms_raw_reading_rule_table_disagreement_unresolved",
                    }
                )
    worked = []
    for case in json.loads((corpus / "worked-cases.json").read_text()):
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
        "classical_acceptance_passed": not differences
        and all(c["passed"] for c in worked),
        "whole_book_conformance": "not_established",
        "scope_limit": "宫位和年序的有限来源核验，不认证全书、分野断法或现实预测。",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "src/fatebridge/core/metaphysics/taiyi_long_cycles.py").read_bytes()
        ).hexdigest(),
    }
