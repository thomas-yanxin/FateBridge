"""Append native readings to every original Wujing target without regrading it."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.audit_taiyi_wujing_cycles import audit as literal_audit
from scripts.audit_taiyi_wujing_cycles import source_data, source_value

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_wujing_facsimile_v46"
SOURCE_SHA = "d27100bd4dd65809c712db2020a8d7bbf87f7941c2f0d3c5aab645b71679be88"
READINGS_SHA = "dda4dace283f83f2b827ee386b8e7bd927177bb763440aab9f354b050574b764"


def verify(corpus: Path = CORPUS) -> dict[str, Any]:
    def read(path: Path) -> dict[str, Any]:
        return dict(json.loads(path.read_text()))

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(corpus / "freeze.json") != SOURCE_SHA:
        raise ValueError("武经书影来源指纹不符")
    frozen = read(corpus / "freeze.json")
    for name, expected in frozen["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"武经书影指纹不符：{name}")
    # Runtime and the evolving requirements ledger are recorded baselines,
    # not source answers. They may change under a future calculation repair.
    for name, expected in frozen["source_pins"].items():
        if name.startswith("src/") or name.endswith("requirements.json"):
            continue
        pinned = ROOT / name
        if sha(pinned) != expected:
            raise ValueError(f"武经既有来源指纹不符：{name}")
    if sha(corpus / "readings-freeze.json") != READINGS_SHA:
        raise ValueError("武经书影选读指纹不符")
    selected = read(corpus / "readings-freeze.json")
    if selected["protocol_freeze_sha256"] != SOURCE_SHA:
        raise ValueError("武经书影协议绑定不符")
    for name, expected in selected["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"武经书影选读指纹不符：{name}")
    for name, expected in selected["name_evidence"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"武经名位旁证指纹不符：{name}")
    readings = read(corpus / "native-readings.json")
    protocol = read(corpus / "protocol.json")
    rows = readings["readings"]
    targets = {(r["id"], r["field"]) for r in protocol["original_unknown_targets"]}
    if len(rows) != 45 or {(r["id"], r["field"]) for r in rows} != targets:
        raise ValueError("武经原45项未知的完整范围不符")
    reference = source_data()["name_reference"]
    for row in rows:
        if not row["pages"] or not row["quote"] or not row["literal"]:
            raise ValueError("武经选读缺少原文或页号")
        if any(f"native/page{n}.png" not in frozen["files"] for n in row["pages"]):
            raise ValueError("武经选读缺少冻结书影")
        value = row["value"]
        if row["resolution"] == "explicit_primary_name":
            resolved = source_value(
                {
                    "field": "shiji_name",
                    "value": row["literal"],
                    "status": "literal_text",
                },
                reference,
            )
            if value is None or resolved["value"] != value:
                raise ValueError("武经选读神名不合独立明列名位")
        elif row["resolution"] == "explicit_numeric_with_interposed_annotation":
            if row["literal"] != "三" or type(value) is not int or value != 3:
                raise ValueError("武经选读独立明列数词不符")
        elif row["resolution"] == "explicit_center_for_both_named_generals":
            if row["literal"] != "中宮" or type(value) is not int or value != 5:
                raise ValueError("武经选读明列中宫不符")
        elif value is not None:
            raise ValueError("未裁定的武经读法不得填入位置或将数")
    return readings


def compare(legacy: dict[str, Any], readings: dict[str, Any]) -> dict[str, Any]:
    """Compare frozen readings against supplied actuals; never derive a source value."""
    original = literal_audit()
    original_comparisons = {
        (row["id"], item["actual_field"]): item
        for row in original["source_rows"]
        for item in row["comparisons"]
    }
    native = {(r["id"], r["field"]): r for r in readings["readings"]}
    rows = []
    targets = []
    totals = {
        key: {"required": 144, "matching": 0, "different": 0, "unknown": 0}
        for key in legacy["field_totals"]
    }
    for row in legacy["source_rows"]:
        comparisons = []
        for old in row["comparisons"]:
            target = native.get((row["id"], old["actual_field"]))
            if target is not None and old["comparison_status"] != "unknown":
                raise ValueError("书影选读不能覆盖旧已评估字段")
            value = (
                target["value"]
                if target is not None
                else old["resolved_source"]["value"]
            )
            actual = old["actual_value"]
            status = (
                "unknown"
                if value is None
                else "matching" if value == actual else "different"
            )
            field = old["source_observation"]["field"]
            totals[field][status] += 1
            item = {
                "original_comparison": copy.deepcopy(
                    original_comparisons[row["id"], old["actual_field"]]
                ),
                "current_literal_comparison": copy.deepcopy(old),
                "native_reading": copy.deepcopy(target),
                "effective_source_value": value,
                "actual_value": actual,
                "comparison_status": status,
            }
            comparisons.append(item)
            if target is not None:
                targets.append({"id": row["id"], "field": old["actual_field"], **item})
        rows.append({"id": row["id"], "comparisons": comparisons})
    if (
        len(rows) != 144
        or any(len(r["comparisons"]) != 10 for r in rows)
        or len(targets) != 45
    ):
        raise ValueError("武经完整1440项比较范围不符")
    return {
        "completion_claim": False,
        "source_freeze_sha256": SOURCE_SHA,
        "readings_freeze_sha256": READINGS_SHA,
        "original_layer": original,
        "current_literal_layer": copy.deepcopy(legacy),
        "required_rows": 144,
        "required_observations": 1440,
        "original_unknown_targets": 45,
        "native_values_clarified": sum(
            r["effective_source_value"] is not None for r in targets
        ),
        "target_comparisons": targets,
        "source_rows": rows,
        "field_totals": totals,
        "old_differences_retained": copy.deepcopy(original["differences"]),
        "unreviewed_other_fields_individually_facsimile_verified": False,
        "all_native_pages_individually_read": False,
        "source_or_production_arithmetic_corrected": False,
        "new_dated_cases": 0,
        "new_model_calls": 0,
        "independent_human_reviews": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_explanation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    return compare(literal_audit(), verify(corpus))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "required_observations": 1440,
                "native_values_clarified": report["native_values_clarified"],
                "whole_classic_acceptance_passed": False,
            }
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
