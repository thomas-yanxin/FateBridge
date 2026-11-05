"""Re-evaluate complete HD physical rows against the unchanged frozen cohort."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from fatebridge.validation.acceptance import (
    GateObservation,
    GateProtocol,
    evaluate_gate,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/human-design-calendar-span-de440.json"
REFERENCE_SHA256 = "06ef8f4e29842187f7916734006d7c56467ead52a7f23797865912a5a5b14411"


def evaluate(report: dict) -> dict:
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("原JPL参考改变；不能更新固定身份绕过验收")
    reference = json.loads(raw)
    if set(report["backends"]) != {"selected", "moshier_diagnostic"}:
        raise ValueError("原两个后端均须保留；不能只验成功分支")
    facts = {
        f"{pair['label']}|{side}|{body}": (pair[side]["jd_tt"], fact["longitude"])
        for pair in reference["pairs"]
        for side in ("personality", "design")
        for body, fact in pair[side]["positions"].items()
    }
    ids = tuple(
        f"{pair['label']}|{side}|{body}"
        for pair in reference["pairs"]
        for side in ("personality", "design")
        for body in pair[side]["positions"]
    )
    gates = []
    for name, backend in report["backends"].items():
        protocol = GateProtocol(
            gate_id=f"original_hd_span.{name}.positions",
            method_id=name,
            axis="numerical",
            reference_sha256=REFERENCE_SHA256,
            case_ids=ids,
            comparison="absolute_error_le",
            tolerance=2.0,
            unit="arcseconds",
            scope="全部原始1200时刻、双侧和10天体；不排除太阳邻近失败，不改参考或2角秒门槛",
        )
        rows = []
        for row in backend["position_rows"]:
            key = f"{row['label']}|{row['side']}|{row['body']}"
            fact = facts.get(key)
            value = row.get("computed_longitude")
            valid = (
                fact is not None
                and row["jd_tt"] == fact[0]
                and isinstance(value, (int, float))
                and math.isfinite(value)
            )
            # Compare the reported computation directly with the sealed JPL
            # coordinate. Never trust a supplied 'passed' or error scalar.
            error = abs(math.remainder(value - fact[1], 360)) * 3600 if valid else None
            flags = row.get("return_flags")
            accepted = type(flags) is int and (flags & 7) == (
                2 if name == "selected" else 4
            )
            rows.append(
                GateObservation(
                    case_id=key,
                    reference_sha256=REFERENCE_SHA256,
                    error=error,
                    unavailable_reason=(
                        None
                        if valid and accepted
                        else "missing_or_inconsistent_calculation_witness"
                    ),
                )
            )
        gates.append(evaluate_gate(protocol, tuple(rows)))
        root_protocol = GateProtocol(
            gate_id=f"original_hd_span.{name}.roots",
            method_id=name,
            axis="numerical",
            reference_sha256=REFERENCE_SHA256,
            case_ids=tuple(pair["label"] for pair in reference["pairs"]),
            comparison="absolute_error_le",
            tolerance=5.0,
            unit="seconds",
            scope="原1200个88度设计时刻根及原5秒线；后端来源仍须通过",
        )
        root_facts = {
            pair["label"]: pair["design"]["jd_tt"] for pair in reference["pairs"]
        }
        root_rows = []
        for row in backend["root_rows"]:
            value = row.get("computed_jd_tt")
            expected = root_facts.get(row["label"])
            valid = (
                expected is not None
                and isinstance(value, (int, float))
                and math.isfinite(value)
            )
            error = abs(value - expected) * 86400 if valid else None
            root_rows.append(
                GateObservation(
                    case_id=row["label"],
                    reference_sha256=REFERENCE_SHA256,
                    error=error,
                    unavailable_reason=(
                        None
                        if valid and row["backend_accepted"]
                        else "missing_or_inconsistent_solar_root_witness"
                    ),
                )
            )
        gates.append(evaluate_gate(root_protocol, tuple(root_rows)))
    return {
        "gates": gates,
        "all_declared_gates_passed": all(g["status"] == "passed" for g in gates),
        "source_and_interpretation_acceptance": "not_assessed_by_this_numeric_gate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    "gate": g["gate_id"],
                    "status": g["status"],
                    "denominator": g["denominator"],
                    "failed": len(g["failures"]),
                    "unresolved": len(g["unresolved"]),
                }
                for g in result["gates"]
            ]
        )
    )
    return 0 if result["all_declared_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
