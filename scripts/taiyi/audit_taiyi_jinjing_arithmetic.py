"""Compare frozen source-derived arithmetic with tables and external runtime facts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_arithmetic_v49"
FREEZE_SHA = "1a0f7c4ddbda302981762e8be8b1ad7c627996ceb87bd74f0a33c4dddd80de4e"


def verify(corpus: Path = CORPUS) -> dict[str, Any]:
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(corpus / "freeze.json") != FREEZE_SHA:
        raise ValueError("金镜独立算路冻结指纹不符")
    frozen = json.loads((corpus / "freeze.json").read_text())
    for name, expected in frozen["files"].items():
        if Path(name).name != name or sha(corpus / name) != expected:
            raise ValueError(f"金镜独立算路来源指纹不符：{name}")
    for name, expected in frozen["source_pins"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"金镜既有来源或原报告指纹不符：{name}")
    data = {
        key: json.loads((corpus / filename).read_text())
        for key, filename in {
            "grid": "reference-grid.json",
            "source": "source-inputs.json",
            "specification": "reference-specification.json",
            "coincident": "all-coincident-source-slots.json",
            "probes": "prior-manual-probes.json",
        }.items()
    }
    controls, rows = data["grid"]["controls"], data["source"]["rows"]
    if (
        len(controls) != 128
        or len({(r["marker"], r["taiyi_number"]) for r in controls}) != 128
    ):
        raise ValueError("金镜128软件对照槽位范围不符")
    if len(rows) != 144 or {(r["yin"], r["ju"]) for r in rows} != {
        (yin, ju) for yin in (False, True) for ju in range(1, 73)
    }:
        raise ValueError("金镜原144局288两算不得减删")
    return data


def trace_agrees(actual: dict[str, Any], reference: dict[str, Any]) -> bool:
    path = actual.get("path")
    return (
        type(actual.get("count")) is int
        and actual["count"] == reference["count"]
        and isinstance(path, list)
        and all(isinstance(p, dict) and type(p.get("value")) is int for p in path)
        and [{"position": p.get("palace"), "value": p["value"]} for p in path]
        == reference["terms"]
        and actual.get("terminal_palace") == reference["terminal_palace"]
        and actual.get("terminal_excluded") is reference["terminal_excluded"]
    )


def compare(
    actuals: dict[str, Any] | None = None, corpus: Path = CORPUS
) -> dict[str, Any]:
    data = verify(corpus)
    grid = {(r["marker"], r["taiyi_number"]): r for r in data["grid"]["controls"]}
    source_rows = data["source"]["rows"]
    boards: dict[str, Any] = {}
    assessments: dict[str, Any] = {}
    grid_comparisons = []
    if actuals is not None:
        if actuals.get("reference_freeze_sha256") != FREEZE_SHA:
            raise ValueError("运行事实未绑定本批冻结参照")
        actual_grid = actuals.get("count_grid", [])
        if any(
            type(r.get("marker")) is not str or type(r.get("taiyi_number")) is not int
            for r in actual_grid
        ):
            raise ValueError("实际对照参数类型不符，布尔不能代替宫数")
        if len(actual_grid) != 128 or {
            (r["marker"], r["taiyi_number"]) for r in actual_grid
        } != set(grid):
            raise ValueError("实际128计数槽位不得减删或重复")
        for key in ("boards", "assessments"):
            values = actuals.get(key, [])
            if len(values) != 144 or {r["id"] for r in values} != {
                r["id"] for r in source_rows
            }:
                raise ValueError("实际144局身份不得减删或重复")
        boards = {r["id"]: r["core"] for r in actuals["boards"]}
        assessments = {r["id"]: r["assessment"] for r in actuals["assessments"]}
        for row in source_rows:
            core, assessment = boards[row["id"]], assessments[row["id"]]
            if type(core.get("taiyi_number")) is not int:
                raise ValueError("实际核心宫数类型不符")
            if (
                core.get("yin_dun") is not row["yin"]
                or type(core.get("kook_number")) is not int
                or core["kook_number"] != row["ju"]
            ):
                raise ValueError("实际局身份与参照不符")
            if (
                assessment.get("case_id") != row["id"]
                or assessment.get("status") != "assessed_selected_table_columns"
                or len(assessment.get("counts", [])) != 2
                or {c["camp"] for c in assessment["counts"]} != {"main", "guest"}
            ):
                raise ValueError("原源位置重算事实的身份或范围不符")
        for actual in actual_grid:
            reference = grid[actual["marker"], actual["taiyi_number"]]
            trace = actual["trace"]
            grid_comparisons.append(
                {
                    "marker": actual["marker"],
                    "taiyi_number": actual["taiyi_number"],
                    "expected_count": reference["count"],
                    "actual_trace": trace,
                    "count_matches": type(trace.get("count")) is int
                    and trace["count"] == reference["count"],
                    "trace_matches": trace_agrees(trace, reference),
                }
            )
    source_counts, positions, core_counts, source_recounts = [], [], [], []
    for row in source_rows:
        source_position = row["positions"]
        if actuals is not None:
            core = boards[row["id"]]
            for field, expected in source_position.items():
                positions.append(
                    {
                        "id": row["id"],
                        "field": field,
                        "source": expected,
                        "actual": core[field],
                        "matches": core[field] == expected,
                    }
                )
        for camp, field in (("main", "wenchang_palace"), ("guest", "shiji")):
            reference = grid[source_position[field], source_position["taiyi_number"]]
            table = row["table_counts"][camp + "_count"]
            source_counts.append(
                {
                    "id": row["id"],
                    "camp": camp,
                    "source_marker": source_position[field],
                    "source_taiyi_number": source_position["taiyi_number"],
                    "source_table_count": table,
                    "independent_count": reference["count"],
                    "independent_terms": reference["terms"],
                    "matches_table": table == reference["count"],
                }
            )
            if actuals is None:
                continue
            core = boards[row["id"]]
            actual_key = (core[field], core["taiyi_number"])
            if actual_key not in grid:
                raise ValueError("实际位置不在冻结128对照范围内")
            expected = grid[actual_key]
            count = core[camp + "_count"]
            core_counts.append(
                {
                    "id": row["id"],
                    "camp": camp,
                    "actual_marker": core[field],
                    "actual_taiyi_number": core["taiyi_number"],
                    "actual_count": count,
                    "independent_count_for_actual_inputs": expected["count"],
                    "engine_arithmetic_matches": type(count) is int
                    and count == expected["count"],
                    "engine_trace_matches": trace_agrees(
                        core["count_trace"][camp], expected
                    ),
                    "source_table_count": table,
                    "actual_matches_table": count == table,
                }
            )
            rec = next(c for c in assessments[row["id"]]["counts"] if c["camp"] == camp)
            recount = rec["source_position_recount"]
            source_recounts.append(
                {
                    "id": row["id"],
                    "camp": camp,
                    "engine_source_recount": recount["count"],
                    "independent_source_recount": reference["count"],
                    "recount_matches": type(recount.get("count")) is int
                    and recount["count"] == reference["count"],
                    "trace_matches": trace_agrees(recount, reference),
                }
            )
    old_path = ROOT / "tests/data/taiyi/known_source_disagreements.json"
    old = json.loads(old_path.read_text())
    return {
        "completion_claim": False,
        "source_freeze_sha256": FREEZE_SHA,
        "required_classical_rows": 144,
        "required_classical_count_slots": 288,
        "required_reference_controls": 128,
        "software_controls_are_new_classical_cases": False,
        "runtime_assessed": actuals is not None,
        "runtime_provenance": (
            copy.deepcopy(actuals.get("provenance")) if actuals else None
        ),
        "reference_controls": grid_comparisons,
        "reference_control_failures": [
            c
            for c in grid_comparisons
            if not c["count_matches"] or not c["trace_matches"]
        ],
        "independent_source_counts": source_counts,
        "independent_source_count_matches": sum(
            c["matches_table"] for c in source_counts
        ),
        "source_internal_disagreements": [
            c for c in source_counts if not c["matches_table"]
        ],
        "source_position_comparisons": positions,
        "actual_core_counts": core_counts,
        "engine_arithmetic_failures": [
            c
            for c in core_counts
            if not c["engine_arithmetic_matches"] or not c["engine_trace_matches"]
        ],
        "production_source_recounts": source_recounts,
        "engine_source_recount_failures": [
            c
            for c in source_recounts
            if not c["recount_matches"] or not c["trace_matches"]
        ],
        "old_11_count_disagreements_retained": old["groups"]["counts"]["differences"],
        "old_3_position_disagreements_retained": old["groups"]["positions"][
            "differences"
        ],
        "same_point_all20_source_slots": data["coincident"],
        "selected_rule_is_complete_classical_adjudication": False,
        "new_dated_cases": 0,
        "new_model_calls": 0,
        "independent_human_reviews": 0,
        "production_arithmetic_changed": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_explanation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actuals-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    actuals = json.loads(args.actuals_file.read_text()) if args.actuals_file else None
    result = compare(actuals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "source_count_matches": result["independent_source_count_matches"],
                "source_count_required": 288,
                "runtime_assessed": result["runtime_assessed"],
                "engine_arithmetic_failures": (
                    len(result["engine_arithmetic_failures"])
                    if result["runtime_assessed"]
                    else None
                ),
                "reference_control_failures": (
                    len(result["reference_control_failures"])
                    if result["runtime_assessed"]
                    else None
                ),
                "complete": False,
            }
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
