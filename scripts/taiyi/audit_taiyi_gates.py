"""Keep every source row, including contradictory gate/year worked readings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_gates import attach_gate_board, gate_cycle
from fatebridge.core.metaphysics.taiyi_year import (
    assemble_board,
    cyclic_core,
    yearly_core,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v5"
CASE_FIELDS = {
    "tongzong-1634-year": {"marker", "count", "general", "vice_general"},
    "key-1561-year": {
        "marker",
        "count",
        "general",
        "vice_general",
        "duty_gate",
        "unit_in_gate",
    },
    "wubeizhi-1571-year": {
        "marker",
        "count",
        "general",
        "vice_general",
        "duty_gate",
        "doors",
        "three_gates",
        "five_generals",
        "menju_jiangfa",
    },
    "key-1561-xu-month": {
        "marker",
        "count",
        "general",
        "vice_general",
        "duty_gate",
        "unit_in_gate",
    },
}


def worked_board(case: dict[str, Any]) -> dict[str, Any]:
    """Numerical example only; this does not enable ancient civil dates."""
    if case["mode"] == "year":
        core = yearly_core(case["year_ce"])
    else:
        core = cyclic_core(case["input_cycle_count"])
        core.update(
            ruler_branch=case["ruler_branch"], ruler_label="月建", heshen=case["heshen"]
        )
    board = assemble_board(core)
    attach_gate_board(board, case["mode"], case.get("year_ce"))
    return board


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    required = {
        "gate-anchors.json",
        "worked-cases.json",
        "tongzong-page31.jpg",
        "tongzong-page32.jpg",
        "key-page38.jpg",
    }
    if not required <= {s["file"] for s in manifest["source_files"]}:
        raise ValueError("独立门表、课例及冲突底图不得移除")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("冻结门法参照指纹不符：" + item["file"])
    anchors = json.loads((corpus / "gate-anchors.json").read_text())["cases"]
    if (
        len(anchors) != 18
        or {c["id"] for c in anchors} != {f"G{i:02d}" for i in range(1, 19)}
        or any(
            not {"raw_era", "year_ce", "ganzhi", "duty_gate", "image", "note"}
            <= c.keys()
            for c in anchors
        )
    ):
        raise ValueError("门表必须完整保留18行及纪年、干支、直门字段")
    anchor_diffs = []
    anchor_results = []
    unevaluated = []
    for case in anchors:
        year = case["year_ce"]
        if year is None:
            unevaluated.append(
                {
                    "id": case["id"],
                    "fields": ["duty_gate", "ganzhi"],
                    "reason": case["note"],
                }
            )
            anchor_results.append(
                {
                    "id": case["id"],
                    "actual": None,
                    "status": "unadjudicated_year_reading",
                }
            )
            continue
        actual = {
            "duty_gate": gate_cycle(3361 + year - 724)["duty_gate"],
            "ganzhi": "甲乙丙丁戊己庚辛壬癸"[(year - 4) % 10]
            + "子丑寅卯辰巳午未申酉戌亥"[(year - 4) % 12],
        }
        for field, value in actual.items():
            if value != case[field]:
                anchor_diffs.append(
                    {
                        "id": case["id"],
                        "raw_era": case["raw_era"],
                        "year_ce": year,
                        "field": field,
                        "source_value": case[field],
                        "derived_value": value,
                        "note": case["note"],
                    }
                )
        anchor_results.append({"id": case["id"], "actual": actual})
    cases = json.loads((corpus / "worked-cases.json").read_text())["cases"]
    if (
        len(cases) != 4
        or {c["id"] for c in cases} != CASE_FIELDS.keys()
        or any(set(c["expected"]) != CASE_FIELDS[c["id"]] for c in cases)
    ):
        raise ValueError("必须保留4条课例及所有已冻结字段，不能删除未通过读数")
    worked_diffs = []
    results = []
    checked = 0
    for case in cases:
        board = worked_board(case)
        det = board["determinate_calculation"]
        actual = {k: det[k] for k in ("marker", "count", "general", "vice_general")}
        actual.update(
            {k: board["gates"]["counter"][k] for k in ("duty_gate", "unit_in_gate")}
        )
        assessment = board["condition_assessment"]
        actual.update(
            doors={
                str(r["number"]): r["door"]
                for r in board["gates"]["moving_frame"]["rows"]
            },
            three_gates=assessment["three_gates"]["conditions_satisfied"],
            five_generals=assessment["five_generals"]["conditions_satisfied"],
            menju_jiangfa=assessment["menju_jiangfa"],
        )
        for field, expected in case["expected"].items():
            values = (
                expected.items() if isinstance(expected, dict) else [(None, expected)]
            )
            for key, target in values:
                checked += 1
                observed = actual[field][key] if key is not None else actual[field]
                if observed != target:
                    worked_diffs.append(
                        {
                            "id": case["id"],
                            "field": field + ("." + key if key is not None else ""),
                            "source_value": target,
                            "derived_value": observed,
                            "note": case.get("note", ""),
                        }
                    )
        results.append(
            {"id": case["id"], "actual": {k: actual[k] for k in case["expected"]}}
        )
    return {
        "completion_claim": False,
        "gate_anchor_list": {
            "total_rows": 18,
            "required_fields": 36,
            "checked_fields": 36 - 2 * len(unevaluated),
            "matching_fields": 36 - 2 * len(unevaluated) - len(anchor_diffs),
            "cases": anchor_results,
            "disagreements": anchor_diffs,
            "unevaluated": unevaluated,
        },
        "selected_worked_examples": {
            "total_cases": 4,
            "checked_fields": checked,
            "matching_fields": checked - len(worked_diffs),
            "cases": results,
            "disagreements": worked_diffs,
        },
        "classical_gate_acceptance_passed": not anchor_diffs
        and not worked_diffs
        and not unevaluated,
        "policy": "分开原门表、选定课例与软件边界测试；保留原读数和版本层次，不改起元来贴表，不合并为全书准确率。",
        "calendar_adapter_validated_for_ancient_dates": False,
        "real_world_efficacy": "not_tested",
        "implementation_sha256": {
            name: hashlib.sha256(
                (ROOT / "src/fatebridge/core/metaphysics" / name).read_bytes()
            ).hexdigest()
            for name in ("taiyi_gates.py", "taiyi_year.py", "taiyi_conditions.py")
        },
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
    return 0 if report["classical_gate_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
