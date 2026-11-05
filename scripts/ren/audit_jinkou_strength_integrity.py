"""Keep witness comparisons separate from synthetic explanation corruptions."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_strength_integrity_v1"
FROZEN = "356fb33a50c0cf47288fe5e1aebf25f60934f54689134903e3880602b3ca3bd8"
POSITIONS = ["人元", "贵神", "将神", "地分"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != FROZEN:
        raise ValueError("Frozen strength-integrity manifest changed")
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(freeze["files"]) | {"freeze.json"}:
        raise ValueError("Frozen strength-integrity inventory changed")
    if any(sha(corpus / n) != d for n, d in freeze["files"].items()):
        raise ValueError("Frozen strength-integrity source changed")
    source = json.loads((corpus / "reference.json").read_text())
    for n, d in source["reference_hashes"].items():
        if sha(ROOT / n) != d:
            raise ValueError("Earlier strength witness changed")
    faults = json.loads((corpus / "faults.json").read_text())["faults"]
    if len(source["cases"]) != 12 or len(faults) != 37:
        raise ValueError("Complete strength-integrity denominators required")
    return dict(
        source=source,
        faults=faults,
        protocol=json.loads((corpus / "protocol.json").read_text()),
    )


def changed(value: Any, operation: str) -> Any:
    if operation == "flip":
        return not value
    if operation == "phase":
        return "木" if value != "木" else "金"
    if operation == "power":
        return "旺" if value != "旺" else "休"
    if operation == "pop":
        if not value:
            raise ValueError("Declared deletion fault has no item to remove")
        return value[:-1]
    if operation == "different_positions":
        return [] if value else ["人元"]
    if operation == "status":
        return {
            "ambiguous_excerpt": "resolved_excerpt",
            "resolved_excerpt": "ambiguous_excerpt",
            "no_control_strength_priority_unresolved": "polarity_and_afflictions_only",
            "polarity_and_afflictions_only": "no_control_strength_priority_unresolved",
        }[value]
    if operation == "increment":
        return value + 1
    if operation == "month_label":
        return "建旺" if value != "建旺" else "月破"
    if operation == "extra_power_role":
        return dict(value, **{"不存在的第五位": "旺"})
    raise ValueError("Unknown declared corruption")


def corrupt(output: dict[str, Any], fault: dict[str, Any]) -> dict[str, Any]:
    # Serialization splits domain aliases, so a trace-only fault is trace-only.
    result: dict[str, Any] = json.loads(json.dumps(output))
    board = result["jinkou"]
    operation = fault["operation"]
    if operation == "coordinated_power":
        power = changed(board["rows"][1]["internal_power"], "power")
        board["rows"][1]["internal_power"] = power
        board["internal_strength"]["powers"]["贵神"] = power
        for trace in board["rule_trace"]:
            if trace["rule_id"] == "jinkou.internal_strength":
                trace["result"]["powers"]["贵神"] = power
        return result
    node = board
    if "trace_rule" in fault:
        trace = next(
            t for t in board["rule_trace"] if t["rule_id"] == fault["trace_rule"]
        )
        if operation == "delete_record":
            board["rule_trace"].remove(trace)
            return result
        if operation == "duplicate_record":
            board["rule_trace"].append(copy.deepcopy(trace))
            return result
        node = trace["result"]
    path = [int(k) if k.isdigit() else k for k in fault["path"]]
    for key in path[:-1]:
        node = node[key]
    key = path[-1]
    if operation == "delete":
        del node[key]
    else:
        node[key] = changed(node[key], operation)
    return result


def audit() -> dict[str, Any]:
    ref = reference()
    watch: tuple[str, ...] = (
        "src/fatebridge/core/output_chinese.py",
        "src/fatebridge/core/output_ren_anchors.py",
        "src/fatebridge/core/metaphysics/jinkou_strength.py",
        "src/fatebridge/core/metaphysics/jinkou_patterns.py",
        "src/fatebridge/core/metaphysics/jinkou_qi.py",
        "src/fatebridge/core/metaphysics/jinkou_sources.py",
        "scripts/ren/audit_jinkou_strength_integrity.py",
    )
    helper = "src/fatebridge/core/output_jinkou_strength.py"
    if (ROOT / helper).exists():
        watch += (helper,)
    before = {n: sha(ROOT / n) for n in watch}
    from fatebridge.application.execution import OutputContractError, validate_output
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "jinkou")
    fn, args, kw = spec.bind(
        spec.request_model.model_validate(ref["protocol"]["payload"])
    )
    output = fn(*args, **kw)
    validate_output(spec, output)
    faults = []
    for fault in ref["faults"]:
        try:
            validate_output(spec, corrupt(output, fault))
        except OutputContractError:
            rejected = True
        else:
            rejected = False
        faults.append(dict(id=fault["id"], rejected=rejected))
    witness = []
    for case in ref["source"]["cases"]:
        actual = internal_strength(
            [
                dict(label=p, element=e)
                for p, e in zip(POSITIONS, case["elements"], strict=True)
            ]
        )
        witness.append(
            dict(
                case,
                actual_anchor=actual["anchor_element"],
                actual_god_power=actual["powers"]["贵神"],
                matched=actual["anchor_element"] == case["stated_anchor"]
                and actual["powers"]["贵神"] == case["stated_god_power"],
            )
        )
    old_spec = importlib.util.spec_from_file_location(
        "old_strength", ROOT / "scripts/ren/audit_jinkou_strength.py"
    )
    assert old_spec and old_spec.loader
    old = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old)
    old_report = old.audit()
    reference()
    return dict(
        synthetic_fault_count=len(faults),
        synthetic_rejected_count=sum(f["rejected"] for f in faults),
        synthetic_faults=faults,
        new_witness_case_count=12,
        new_witness_matched_count=sum(c["matched"] for c in witness),
        new_witness_comparisons=witness,
        older_scan_case_count=old_report["scan_case_count"],
        older_scan_matched_count=old_report["scan_matched_count"],
        older_scan_failures=old_report["scan_failures"],
        engineering_rejection_gate_passed=all(f["rejected"] for f in faults),
        original_classical_gate_passed=old_report["classical_acceptance_passed"],
        daily_five_states_adjudicated=False,
        comprehensive_use_adjudicated=False,
        new_unique_historical_or_empirical_events=0,
        goal_complete=False,
        model_invocations=0,
        implementation_sha256=before,
        implementation_unchanged=before == {n: sha(ROOT / n) for n in watch},
        source_freeze_sha256=FROZEN,
    )
