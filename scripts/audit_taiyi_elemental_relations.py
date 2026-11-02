"""Separate literal examples, synthetic graph tests, and software coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.taiyi_elemental_relations import (
    element_relation,
    elemental_guan_assessment,
)
from fatebridge.core.metaphysics.taiyi_year import cyclic_core, structural_patterns

if TYPE_CHECKING:
    from .build_taiyi_elemental_relations import CORPUS, source_data
elif __package__:
    from .build_taiyi_elemental_relations import CORPUS, source_data
else:
    from build_taiyi_elemental_relations import CORPUS, source_data


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = source_data(corpus)
    rows = []
    for case in data["worked_examples"]:
        a = elemental_guan_assessment(
            {
                "wenchang_palace": case["main"]["position"],
                "shiji": case["guest"]["position"],
            },
            calculation_mode="day",
        )
        observed = {e["camp"]: e for e in a["eyes"]}
        rows.append(
            {
                "id": case["id"],
                "source_profile": case["profile"],
                "source_quote": case["quote"],
                "source_tendency": case["source_tendency"],
                "source_labels": {
                    camp: case[camp]["source_label"] for camp in ["main", "guest"]
                },
                "source_fields": 5,
                "given_position_inputs": {
                    c: case[c]["position"] for c in ["main", "guest"]
                },
                "computed_fields": 3,
                "matched_computed_fields": sum(
                    observed[c]["element"] == case[c]["element"]
                    for c in ["main", "guest"]
                )
                + int(a["relation"] == case["relation"]),
                "expected_relation": case["relation"],
                "actual_relation": a["relation"],
                "interpretation": a["source_interpretation"],
            }
        )
    truth = json.loads((corpus / "synthetic-truth.json").read_text())["rows"]
    synthetic = [
        {
            **r,
            "actual": element_relation(r["main"], r["guest"]),
            "matches": element_relation(r["main"], r["guest"]) == r["expected"],
        }
        for r in truth
    ]
    software = []
    for yin in [False, True]:
        for ju in range(1, 73):
            c = cyclic_core(ju, yin=yin)
            p = structural_patterns(c)
            a = elemental_guan_assessment(c, p)
            software.append(
                {
                    "yin": yin,
                    "ju": ju,
                    "relation": a["relation"],
                    "elemental_control": a["elemental_control"],
                    "implemented_spatial_guan": a["implemented_spatial_guan"][
                        "present"
                    ],
                    "time_method_not_supplied": a["source_day_usage"]
                    == "time_method_not_supplied",
                }
            )
    return {
        "completion_claim": False,
        "source_spirit_elements": len(data["spirit_elements"]),
        "literal_examples": len(rows),
        "literal_source_fields": sum(r["source_fields"] for r in rows),
        "given_position_inputs": 8,
        "computed_literal_fields": sum(r["computed_fields"] for r in rows),
        "matched_computed_literal_fields": sum(
            r["matched_computed_fields"] for r in rows
        ),
        "source_rows": rows,
        "synthetic_relations": len(synthetic),
        "matching_synthetic_relations": sum(r["matches"] for r in synthetic),
        "synthetic_rows": synthetic,
        "software_cyclic_boards": len(software),
        "software_rows": software,
        "software_with_elemental_control_without_implemented_spatial_guan": sum(
            r["elemental_control"] and not r["implemented_spatial_guan"]
            for r in software
        ),
        "count_policy": "4条源文例20源字段中8位置为输入、12为元素/关系输出；16神分类、25合成关系及144软件盘分列；不相加为独立古例或准确率。",
        "full_daily_na_yin_method_verified": False,
        "matrix_128_cells_accepted": False,
        "whole_classic_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
