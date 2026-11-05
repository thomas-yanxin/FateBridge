"""Full unchanged DE440 position population under an explicit alternate model."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from fatebridge.core.human_design_point_mass import (
    METHOD_ID,
    point_mass_positions,
    solve_point_mass_design_root,
)
from fatebridge.validation.acceptance import (
    GateObservation,
    GateProtocol,
    evaluate_gate,
)

REFERENCE_SHA256 = "06ef8f4e29842187f7916734006d7c56467ead52a7f23797865912a5a5b14411"
REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/human-design-calendar-span-de440.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("原参考改变；不能更新摘要绕过验收")
    reference = json.loads(raw)
    ids = tuple(
        f"{pair['label']}|{side}|{body}"
        for pair in reference["pairs"]
        for side in ("personality", "design")
        for body in pair[side]["positions"]
    )
    protocol = GateProtocol(
        gate_id="hd_original_population.explicit_sun_monopole.fixed_tt_positions",
        method_id=METHOD_ID,
        axis="numerical",
        reference_sha256=REFERENCE_SHA256,
        case_ids=ids,
        comparison="absolute_error_le",
        tolerance=2.0,
        unit="arcseconds",
        scope="原1200时刻双侧10天体同TT；不重算设计根，不替代原Swiss与Moshier门禁，不证明原典优先或物理误差界",
    )
    rows = []
    observations = []
    for pair in reference["pairs"]:
        for side in ("personality", "design"):
            result = point_mass_positions(pair[side]["jd_tt"])
            if result["status"] != "computed":
                raise RuntimeError(result)
            for position in result["positions"]:
                body = position["body"]
                value = position["longitude"]
                expected = pair[side]["positions"][body]["longitude"]
                error = abs(math.remainder(value - expected, 360)) * 3600
                key = f"{pair['label']}|{side}|{body}"
                rows.append(
                    {
                        "case_id": key,
                        "jd_tt": pair[side]["jd_tt"],
                        "computed_longitude": value,
                        "reference_longitude": expected,
                        "error_arcseconds": error,
                        "input_state_return_flags": position[
                            "input_state_return_flags"
                        ],
                    }
                )
                observations.append(
                    GateObservation(
                        case_id=key,
                        reference_sha256=REFERENCE_SHA256,
                        error=error,
                    )
                )
    gate = evaluate_gate(protocol, tuple(observations))
    root_protocol = GateProtocol(
        gate_id="hd_original_population.explicit_sun_monopole.design_roots",
        method_id="human_design_point_mass_design_root_v1",
        axis="numerical",
        reference_sha256=REFERENCE_SHA256,
        case_ids=tuple(pair["label"] for pair in reference["pairs"]),
        comparison="absolute_error_le",
        tolerance=5.0,
        unit="seconds",
        scope="全部原1200个88度根，原5秒线；太阳求根全程采用候选自己的坐标，不借用原生或参考设计TT",
    )
    root_rows, root_observations = [], []
    composed_rows = [row for row in rows if "|personality|" in row["case_id"]]
    composed_observations = [
        row for row in observations if "|personality|" in row.case_id
    ]
    for pair in reference["pairs"]:
        solved = solve_point_mass_design_root(pair["personality"]["jd_tt"])
        if solved["status"] != "computed":
            raise RuntimeError(solved)
        tt = solved["design_jd_tt"]
        error = abs(tt - pair["design"]["jd_tt"]) * 86400
        flags = solved["input_state_return_flags_observed"]
        accepted = bool(flags) and all(
            type(f) is int and f & 7 in (1, 2) for f in flags
        )
        root_rows.append(
            {"case_id": pair["label"], "root": solved, "error_seconds": error}
        )
        root_observations.append(
            GateObservation(
                case_id=pair["label"],
                reference_sha256=REFERENCE_SHA256,
                error=error,
                unavailable_reason=(
                    None if accepted else "candidate_solar_source_unverified"
                ),
            )
        )
        derived = point_mass_positions(tt)
        for position in derived["positions"]:
            body, value = position["body"], position["longitude"]
            key = f"{pair['label']}|design|{body}"
            expected = pair["design"]["positions"][body]["longitude"]
            position_error = abs(math.remainder(value - expected, 360)) * 3600
            composed_rows.append(
                {
                    "case_id": key,
                    "jd_tt": tt,
                    "computed_longitude": value,
                    "reference_longitude": expected,
                    "error_arcseconds": position_error,
                    "input_state_return_flags": position["input_state_return_flags"],
                }
            )
            composed_observations.append(
                GateObservation(
                    case_id=key,
                    reference_sha256=REFERENCE_SHA256,
                    error=position_error,
                )
            )
    root_gate = evaluate_gate(root_protocol, tuple(root_observations))
    composed_protocol = protocol.model_copy(
        update={
            "gate_id": "hd_original_population.explicit_sun_monopole.self_solved_chart_positions",
            "scope": "全部原24000位置与原2角秒线；设计侧使用候选自己求出的88度根，非固定参考TT；人格侧不变",
        }
    )
    composed_gate = evaluate_gate(composed_protocol, tuple(composed_observations))
    gates = [gate, root_gate, composed_gate]
    report = {
        "gate": gate,
        "gates": gates,
        "protocol": protocol.model_dump(mode="json"),
        "root_protocol": root_protocol.model_dump(mode="json"),
        "composed_protocol": composed_protocol.model_dump(mode="json"),
        "rows": rows,
        "root_rows": root_rows,
        "self_solved_chart_position_rows": composed_rows,
        "maximum_error_row": max(rows, key=lambda row: row["error_arcseconds"]),
        "maximum_root_error_row": max(root_rows, key=lambda row: row["error_seconds"]),
        "maximum_self_solved_position_error_row": max(
            composed_rows, key=lambda row: row["error_arcseconds"]
        ),
        "original_native_gate_reclassified_as_passed": False,
        "new_profile_design_roots_assessed": True,
        "all_candidate_numeric_gates_passed": all(
            g["status"] == "passed" for g in gates
        ),
        "physical_accuracy_certified": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "gates": gates,
                "maximum_position_error_row": report["maximum_error_row"],
                "maximum_root_error_seconds": report["maximum_root_error_row"][
                    "error_seconds"
                ],
                "maximum_self_solved_position_error_row": report[
                    "maximum_self_solved_position_error_row"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["all_candidate_numeric_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
