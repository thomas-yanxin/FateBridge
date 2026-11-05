"""Source-only, conditional count diagnostics; never import the production engine."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_wujing_internal_v48"
FREEZE_SHA = "9d1302c6d19fcdea9ad2c6799eac9ee0564be24fb5606d48f42b6050e7f42e0d"
HYPOTHESES = ("literal_v18_names", "swap_only_yin_yang_de")


def verify(corpus: Path = CORPUS) -> dict[str, Any]:
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(corpus / "freeze.json") != FREEZE_SHA:
        raise ValueError("武经书内算路冻结指纹不符")
    frozen = json.loads((corpus / "freeze.json").read_text())
    for name, expected in frozen["files"].items():
        if Path(name).name != name or sha(corpus / name) != expected:
            raise ValueError(f"武经书内算路来源指纹不符：{name}")
    for name, expected in frozen["source_pins"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"武经既有来源与原报告指纹不符：{name}")
    data = {
        key: json.loads((corpus / filename).read_text())
        for key, filename in {
            "cohort": "source-cohort.json",
            "profile": "name-profile.json",
            "reference": "conditional-reference.json",
            "readings": "readings.json",
        }.items()
    }
    rows = data["cohort"]["source_rows"]
    if (
        len(rows) != 144
        or {(r["polarity"], r["ju"]) for r in rows}
        != {(polarity, ju) for polarity in ("yang", "yin") for ju in range(1, 73)}
        or len({r["id"] for r in rows}) != 144
        or any(set(r["camps"]) != {"main", "guest"} for r in rows)
    ):
        raise ValueError("武经144局288个原两算槽位不得减删")
    return data


def name_position(literal: Any, profile: dict[str, Any], hypothesis: str) -> str | None:
    if hypothesis not in HYPOTHESES:
        raise ValueError("未预登记的名位假设")
    if not isinstance(literal, str):
        return None
    normalized = literal.translate(str.maketrans(profile["glyph_only_normalization"]))
    candidates = [e for e in profile["entries"] if normalized.startswith(e["name"])]
    if len(candidates) != 1:
        return None
    entry = candidates[0]
    if hypothesis == "swap_only_yin_yang_de":
        if entry["name"] == "陰德":
            return "乾"
        if entry["name"] == "陽德":
            return "丑"
    return str(entry["position"])


def count_trace(
    start: str | None, stop: str | None, reference: dict[str, Any]
) -> dict[str, Any]:
    """Apply the frozen conditional walk, without a source count as an input."""
    points = reference["points_in_declared_forward_order"]
    if start not in points or stop not in reference["palace_numbers"]:
        return {"value": None, "reason": "source_position_unknown", "steps": []}
    if start == stop:
        return {"value": None, "reason": "same_start_stop_unadjudicated", "steps": []}
    index = points.index(start)
    steps = []
    for offset in range(16):
        position = points[(index + offset) % 16]
        if position == stop:
            break
        weight = reference["palace_numbers"].get(position, 1 if offset == 0 else 0)
        steps.append({"position": position, "value": weight})
    return {
        "value": sum(s["value"] for s in steps),
        "reason": "conditional_forward_count",
        "steps": steps,
    }


def observation(
    identifier: str, camp: str, source_count: Any, trace: dict[str, Any]
) -> dict[str, Any]:
    value = trace["value"]
    status = (
        "unknown"
        if value is None or type(source_count) is not int
        else "matching" if value == source_count else "different"
    )
    return {
        "id": identifier,
        "camp": camp,
        "literal_source_count": source_count,
        "conditional_count": trace,
        "comparison_status": status,
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    data = verify(corpus)
    reference = data["reference"]
    positions = {
        number: position for position, number in reference["palace_numbers"].items()
    }
    hypotheses = []
    for hypothesis in HYPOTHESES:
        rows = []
        for row in data["cohort"]["source_rows"]:
            stop = positions.get(row["taiyi_number"])
            for camp, entry in row["camps"].items():
                start = (
                    name_position(entry["literal_name"], data["profile"], hypothesis)
                    if entry["role_established"]
                    else None
                )
                item = observation(
                    row["id"],
                    camp,
                    entry["source_count"],
                    count_trace(start, stop, reference),
                )
                item.update(
                    {
                        "name_literal": entry["literal_name"],
                        "role_established": entry["role_established"],
                        "conditional_start": start,
                        "source_taiyi_number": row["taiyi_number"],
                        "stop": stop,
                    }
                )
                rows.append(item)
        counts = {
            status: sum(r["comparison_status"] == status for r in rows)
            for status in ("matching", "different", "unknown")
        }
        if len(rows) != 288 or len({(r["id"], r["camp"]) for r in rows}) != 288:
            raise ValueError("武经两算完整分母不符")
        hypotheses.append(
            {
                "hypothesis": hypothesis,
                "required_count_slots": 288,
                "totals": counts,
                "source_rows": rows,
                "complete_count_method_adjudicated": False,
            }
        )
    worked = []
    for edition, readings in data["readings"]["yang4"].items():
        for hypothesis in HYPOTHESES:
            for camp in ("main", "guest"):
                start = name_position(
                    readings[camp + "_name"], data["profile"], hypothesis
                )
                item = observation(
                    "yang-4",
                    camp,
                    readings[camp + "_count"],
                    count_trace(start, positions[readings["taiyi_number"]], reference),
                )
                item.update(
                    {
                        "edition": edition,
                        "hypothesis": hypothesis,
                        "native_pages": readings["pages"],
                    }
                )
                worked.append(item)
    return {
        "completion_claim": False,
        "source_freeze_sha256": FREEZE_SHA,
        "method": "conditional_source_self_consistency_without_production",
        "required_rows": 144,
        "required_count_slots": 288,
        "original_1440_comparison_requirement_retained": True,
        "hypotheses": hypotheses,
        "selected_hypothesis": None,
        "worked_edition_comparisons": worked,
        "source_readings": data["readings"],
        "conditional_reference": reference,
        "source_erratum_adjudicated": False,
        "production_algorithm_executed": False,
        "production_results_used_as_expected": False,
        "production_arithmetic_changed": False,
        "old_scores_regraded": False,
        "new_independent_dated_cases": 0,
        "new_model_calls": 0,
        "independent_human_reviews": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_explanation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "hypotheses": [
                    {"id": h["hypothesis"], **h["totals"]} for h in report["hypotheses"]
                ],
                "source_erratum_adjudicated": False,
            }
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
