"""Audit every source cell without counting copied text as calculated accuracy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.taiyi_victory_matrix import victory_matrix_assessment
from fatebridge.core.metaphysics.taiyi_year import (
    PALACES,
    count_to_taiyi,
    general_for_count,
)

if TYPE_CHECKING:
    from scripts.taiyi.build_taiyi_victory_matrix import CORPUS, source_data
from scripts.taiyi.build_taiyi_victory_matrix import CORPUS, source_data


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = source_data(corpus)
    rows = []
    for cell in data["cells"]:
        eye, n = cell["wenchang_position"], cell["taiyi_number"]
        path = count_to_taiyi(eye, n)
        general = general_for_count(path["count"])
        # The table supplies no guest eye or dated full board. Do not invent one.
        core = {
            "wenchang_palace": eye,
            "taiyi_number": n,
            "taiyi_palace": PALACES[n],
            "main_general": general,
            "main_vice_general": general * 3 % 10,
        }
        a = victory_matrix_assessment(core)
        assert a["source_cell"] == cell
        rows.append(
            {
                "cell": cell,
                "actual_main_count": path,
                "main_general": general,
                "main_vice_general": core["main_vice_general"],
                "geometry": a["actual_geometry"],
                "clauses": a["clauses"],
                "comparison": a["comparison_summary"],
            }
        )
    clauses = [c for row in rows for c in row["clauses"]]
    eye_claims = [
        c for c in clauses if c.get("role_resolution") == "table_eye_wenchang"
    ]
    generals = [c for c in clauses if c.get("role_resolution") == "camp_unadjudicated"]
    candidates = [
        v for c in generals for v in c["candidates"] if v["field"].startswith("main_")
    ]
    return {
        "completion_claim": False,
        "source_cells": len(rows),
        "retrieved_source_cells": len(rows),
        "copied_source_fields_counted_as_calculated_hits": 0,
        "source_eye_geometric_clauses": len(eye_claims),
        "matching_eye_geometry": sum(
            c["candidates"][0]["matches_geometry"] is True for c in eye_claims
        ),
        "different_eye_geometry": sum(
            c["candidates"][0]["matches_geometry"] is False for c in eye_claims
        ),
        "unqualified_general_clauses": len(generals),
        "hypothetical_main_general_predicates": len(candidates),
        "hypothetical_main_matching_geometry": sum(
            v["matches_geometry"] is True for v in candidates
        ),
        "hypothetical_main_different_geometry": sum(
            v["matches_geometry"] is False for v in candidates
        ),
        "hypothetical_main_unknown_geometry": sum(
            v["matches_geometry"] is None for v in candidates
        ),
        "unadjudicated_fragments": sum(
            c["kind"] == "unadjudicated_clause" for c in clauses
        ),
        "blank_columns": sum(c["kind"] == "blank_retained" for c in clauses),
        "source_lacuna_cells": sum(row["comparison"]["source_lacuna"] for row in rows),
        "count_policy": "128格是书影录文/查表覆盖，不是128个日期古例或128次算对；几何条文、未标客主将的候选比较、空栏和未决片段分别计。",
        "arithmetic_policy": "卷二通则产生主算与主将，仅检验一种明确主方候选；客目缺失，客将保持未知；不把主方较合反推原文客主，不以钤表改主客算。",
        "source_rows": rows,
        "whole_cell_conformance_assessed": False,
        "matrix_128_cells_accepted": False,
        "whole_classic_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
