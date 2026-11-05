"""Compare original values exactly while allowing only declared added evidence.

This does not accept a changed contact set or validate the supplementary probes.
Complete-result verification and independent numerical checks remain separate.
"""

from __future__ import annotations

import argparse
import gzip
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

LEGACY_SCOPE = "交会/驻点收敛至观测零值或相邻TT，分别取最小精确角残差/速度端点，平局取早；仅同一零值去重。黄经量化可掩盖极近峰值，不认证连续根数量、物理精度或传统首末触优先性。"
CURRENT_SCOPE = "交会/速度驻点收敛至观测零值或相邻TT；速度零点不等于返回黄经极值，另在同一变号区间作有限坐标探查，只以严格更极端的已观察坐标补充分段。连续已观察零端点合为一候选，不认证其连续零区间；motion取原生速度符号，另列搜索段相位方向。黄经量化可掩盖极近峰值，不认证连续根数量、物理精度或传统首末触优先性。"


def exact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def original_body_projection(
    current: dict[str, Any], original: dict[str, Any]
) -> dict[str, Any]:
    if (
        original["numerical_scope"] != LEGACY_SCOPE
        or current["numerical_scope"] != CURRENT_SCOPE
    ):
        raise ValueError("Unreviewed numerical-scope declaration")
    result = deepcopy(current)
    result["numerical_scope"] = LEGACY_SCOPE
    if len(current["contacts"]) != len(original["contacts"]):
        raise ValueError("Changed contact set requires separate acceptance")
    for contact in result["contacts"]:
        evidence = contact.pop("motion_evidence")
        if evidence["motion_basis"] != "native_returned_longitude_speed_sign":
            raise ValueError("Native motion meaning changed")
    if len(current["station_witnesses"]) != len(original["station_witnesses"]):
        raise ValueError("Original station count changed")
    for station in result["station_witnesses"]:
        probe = station.pop("coordinate_probe")
        if probe["baseline_observation_prefix_preserved"] is not True:
            raise ValueError("Observation prefix not preserved")
    old_rows, new_rows = (
        original["evaluation_witnesses"],
        result["evaluation_witnesses"],
    )
    before, after = {r[0]: r for r in old_rows}, {r[0]: r for r in new_rows}
    if len(before) != len(old_rows) or len(after) != len(new_rows):
        raise ValueError("Duplicate observation time")
    for t, row in before.items():
        if t not in after or exact(after[t]) != exact(row):
            raise ValueError(f"Original observation changed/missing: {t}")
    indices = result["evaluation_source_context_indices"]
    if len(indices) != len(new_rows):
        raise ValueError("Observation/source-index lengths differ")
    keep = [i for i, row in enumerate(new_rows) if row[0] in before]
    result["evaluation_witnesses"] = [new_rows[i] for i in keep]
    result["evaluation_source_context_indices"] = [indices[i] for i in keep]
    if exact(result) != exact(original):
        raise ValueError("Original body fields changed outside declared additions")
    return result


def load(path: Path) -> dict[str, Any]:
    raw = (
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Expected an object packet")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before, after = load(args.before), load(args.after)
    results = []
    for old, new in zip(
        before["cycle_context"]["bodies"], after["cycle_context"]["bodies"], strict=True
    ):
        try:
            original_body_projection(new, old)
            results.append({"body": old["body"], "all_original_values_exact": True})
        except (ValueError, KeyError) as error:
            results.append(
                {
                    "body": old["body"],
                    "all_original_values_exact": False,
                    "reason": str(error),
                }
            )
    args.output.write_text(
        json.dumps(
            {
                "results": results,
                "scope": "Exact original-body preservation only; changed contact sets remain unaccepted by this projection.",
            },
            indent=2,
        )
        + "\n"
    )
    raise SystemExit(0 if all(r["all_original_values_exact"] for r in results) else 1)


if __name__ == "__main__":
    main()
